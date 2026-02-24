#!/usr/bin/env python3
"""
Minimal reproduction of heredoc hanging issue with PTY-based terminal on macOS.

This script demonstrates that when a heredoc command is sent to a PTY as a single
write, the heredoc terminator (EOF) is not recognized and the command hangs.

This affects OpenHands SDK's SubprocessTerminal on macOS (when tmux is not available).

Usage:
    python3 heredoc_pty_issue.py

Expected output on affected systems:
    - Simple echo command: PASSES
    - Heredoc command: HANGS (times out after 5 seconds)
"""

import fcntl
import os
import platform
import pty
import select
import subprocess
import sys
import time


def get_environment_info():
    """Gather diagnostic information about the environment."""
    info = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "machine": platform.machine(),
    }
    
    # Get bash version
    try:
        result = subprocess.run(
            ["bash", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        info["bash_version"] = result.stdout.split("\n")[0]
    except Exception as e:
        info["bash_version"] = f"Error: {e}"
    
    # Check if tmux is available
    try:
        result = subprocess.run(
            ["tmux", "-V"],
            capture_output=True,
            text=True,
            timeout=5
        )
        info["tmux_available"] = True
        info["tmux_version"] = result.stdout.strip()
    except FileNotFoundError:
        info["tmux_available"] = False
        info["tmux_version"] = "Not installed"
    except Exception as e:
        info["tmux_available"] = False
        info["tmux_version"] = f"Error: {e}"
    
    return info


class PTYTerminal:
    """Minimal PTY terminal implementation similar to OpenHands SubprocessTerminal."""
    
    def __init__(self):
        self.master_fd = None
        self.pid = None
    
    def start(self):
        """Start a bash shell in a PTY."""
        master_fd, slave_fd = pty.openpty()
        
        pid = os.fork()
        if pid == 0:
            # Child process
            os.close(master_fd)
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            os.close(slave_fd)
            os.execv("/bin/bash", ["/bin/bash", "--norc", "--noprofile"])
        
        # Parent process
        os.close(slave_fd)
        self.master_fd = master_fd
        self.pid = pid
        
        # Set non-blocking
        flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
        fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Wait for shell to initialize
        time.sleep(0.5)
        self._drain_output()
    
    def _drain_output(self):
        """Read and discard any pending output."""
        output = b""
        try:
            while True:
                data = os.read(self.master_fd, 4096)
                if not data:
                    break
                output += data
        except (BlockingIOError, OSError):
            pass
        return output
    
    def send_command(self, command: str, timeout_seconds: float = 5.0) -> tuple[bool, str]:
        """
        Send a command and wait for it to complete.
        
        This mimics how OpenHands SubprocessTerminal sends commands:
        - The entire command is written as a single blob
        - A newline is appended
        
        Returns:
            (success: bool, output: str)
        """
        # Send the command as a single write (this is what OpenHands does)
        payload = command.encode("utf-8") + b"\n"
        os.write(self.master_fd, payload)
        
        # Wait for output with timeout
        start_time = time.time()
        output = b""
        last_output_time = start_time
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                return False, output.decode("utf-8", errors="replace")
            
            # Check for readable data
            readable, _, _ = select.select([self.master_fd], [], [], 0.1)
            if readable:
                try:
                    data = os.read(self.master_fd, 4096)
                    if data:
                        output += data
                        last_output_time = time.time()
                except (BlockingIOError, OSError):
                    pass
            
            # Check if command completed (simple heuristic: no new output for 0.5s
            # and output contains a shell prompt indicator)
            time_since_last_output = time.time() - last_output_time
            if time_since_last_output > 0.5 and output:
                # Check for bash prompt ($ at end of line)
                decoded = output.decode("utf-8", errors="replace")
                lines = decoded.strip().split("\n")
                if lines and lines[-1].rstrip().endswith("$"):
                    return True, decoded
        
        return False, output.decode("utf-8", errors="replace")
    
    def close(self):
        """Clean up the terminal."""
        if self.master_fd is not None:
            try:
                os.write(self.master_fd, b"exit\n")
                time.sleep(0.2)
            except:
                pass
            try:
                os.close(self.master_fd)
            except:
                pass
        if self.pid is not None:
            try:
                os.waitpid(self.pid, os.WNOHANG)
            except:
                pass


def test_simple_command(terminal: PTYTerminal) -> bool:
    """Test that simple commands work."""
    print("  Sending: echo 'hello world'")
    success, output = terminal.send_command("echo 'hello world'", timeout_seconds=5)
    has_output = "hello world" in output
    print(f"  Completed before timeout: {success}")
    print(f"  Output contains expected text: {has_output}")
    # For simple commands, we just check if output appeared
    return has_output


def test_heredoc_command(terminal: PTYTerminal, verbose: bool = False) -> bool:
    """Test heredoc command - short heredocs may work, but we check for proper completion."""
    heredoc_cmd = """cat << 'EOF'
hello from heredoc
EOF"""
    print(f"  Sending heredoc command:")
    for line in heredoc_cmd.split("\n"):
        print(f"    {line}")
    
    success, output = terminal.send_command(heredoc_cmd, timeout_seconds=5)
    has_output = "hello from heredoc" in output
    # Check if the PS1 prompt appeared (indicating command completed)
    has_prompt = "###PS1END###" in output
    
    print(f"  Completed before timeout: {success}")
    print(f"  Output contains expected text: {has_output}")
    print(f"  Shell prompt appeared: {has_prompt}")
    
    if verbose:
        print(f"  Raw output: {output!r}")
    
    # Short heredocs may actually work - check if prompt appeared
    if has_output and has_prompt:
        print("  NOTE: Short heredoc worked (prompt appeared)")
        return True
    
    if not success:
        print("  ISSUE: Command timed out - heredoc may have hung")
        return False
    return has_output


def test_heredoc_with_following_command(terminal: PTYTerminal) -> bool:
    """Test heredoc followed by another command - this pattern is common in agent workflows."""
    heredoc_cmd = """cat > /tmp/test_heredoc_issue.py << 'EOF'
print("hello from python")
EOF
python3 /tmp/test_heredoc_issue.py"""
    print(f"  Sending heredoc + python command:")
    for line in heredoc_cmd.split("\n"):
        print(f"    {line}")
    
    success, output = terminal.send_command(heredoc_cmd, timeout_seconds=10)
    has_python_output = "hello from python" in output
    has_prompt = "###PS1END###" in output
    
    print(f"  Completed before timeout: {success}")
    print(f"  Python script executed: {has_python_output}")
    print(f"  Shell prompt appeared: {has_prompt}")
    
    # If output and prompt both appeared, it worked
    if has_python_output and has_prompt:
        print("  NOTE: Heredoc + command worked (prompt appeared)")
        return True
    
    if not success and not has_python_output:
        print("  ISSUE: Command timed out - heredoc blocked subsequent python command")
        return False
    
    return has_python_output


def test_long_heredoc(terminal: PTYTerminal) -> bool:
    """Test a longer heredoc similar to what agents generate (100+ lines)."""
    # Generate a multi-line Python script similar to agent patterns
    python_code_lines = [
        "import sys",
        "",
        "def process_file():",
        '    """Process a file with multiple operations."""',
        "    lines = []",
    ]
    # Add ~50 lines of code
    for i in range(50):
        python_code_lines.append(f"    # Processing step {i}")
        python_code_lines.append(f"    lines.append('step_{i}')")
    
    python_code_lines.extend([
        "",
        "    return lines",
        "",
        "if __name__ == '__main__':",
        "    result = process_file()",
        "    print(f'Processed {len(result)} steps')",
        "    print('LONG_HEREDOC_SUCCESS')",
    ])
    
    python_code = "\n".join(python_code_lines)
    heredoc_cmd = f"""cat > /tmp/test_long_heredoc.py << 'EOF'
{python_code}
EOF
python3 /tmp/test_long_heredoc.py"""
    
    num_lines = len(heredoc_cmd.split("\n"))
    print(f"  Sending {num_lines}-line heredoc + python command")
    print(f"  (This simulates the long heredocs that agents often generate)")
    
    success, output = terminal.send_command(heredoc_cmd, timeout_seconds=30)
    has_success_marker = "LONG_HEREDOC_SUCCESS" in output
    print(f"  Completed before timeout: {success}")
    print(f"  Python script executed successfully: {has_success_marker}")
    
    if not success:
        print(f"  ISSUE: {num_lines}-line heredoc timed out")
        print("         Long heredocs are common in agent-generated code")
        return False
    return has_success_marker


def main():
    print("=" * 70)
    print("Heredoc PTY Issue Reproduction Script")
    print("=" * 70)
    print()
    
    # Print environment info
    print("Environment Information:")
    print("-" * 40)
    env_info = get_environment_info()
    for key, value in env_info.items():
        print(f"  {key}: {value}")
    print()
    
    if env_info.get("tmux_available"):
        print("NOTE: tmux is available on this system.")
        print("      OpenHands will use TmuxTerminal which doesn't have this issue.")
        print("      To reproduce the SubprocessTerminal issue, temporarily rename tmux.")
        print()
    
    # Run tests
    print("Running Tests:")
    print("-" * 40)
    
    terminal = PTYTerminal()
    try:
        terminal.start()
        
        # Test 1: Simple command (should pass)
        print("\nTest 1: Simple echo command")
        test1_passed = test_simple_command(terminal)
        
        # Need a fresh terminal for the next test since the previous one may have
        # left the shell in a bad state
        terminal.close()
        terminal = PTYTerminal()
        terminal.start()
        
        # Test 2: Heredoc command (expected to fail on affected systems)
        print("\nTest 2: Heredoc command")
        test2_passed = test_heredoc_command(terminal, verbose=True)
        
        # Fresh terminal again
        terminal.close()
        terminal = PTYTerminal()
        terminal.start()
        
        # Test 3: Heredoc followed by command (common agent pattern)
        print("\nTest 3: Heredoc + subsequent command (agent workflow pattern)")
        test3_passed = test_heredoc_with_following_command(terminal)
        
        # Fresh terminal again
        terminal.close()
        terminal = PTYTerminal()
        terminal.start()
        
        # Test 4: Long heredoc (realistic agent pattern)
        print("\nTest 4: Long heredoc (~110 lines, realistic agent pattern)")
        test4_passed = test_long_heredoc(terminal)
        
    finally:
        terminal.close()
    
    # Summary
    print()
    print("=" * 70)
    print("Summary:")
    print("-" * 40)
    print(f"  Test 1 (simple command):     {'PASS' if test1_passed else 'FAIL'}")
    print(f"  Test 2 (heredoc):            {'PASS' if test2_passed else 'FAIL'}")
    print(f"  Test 3 (heredoc + command):  {'PASS' if test3_passed else 'FAIL'}")
    print(f"  Test 4 (long heredoc):       {'PASS' if test4_passed else 'FAIL'}")
    print()
    
    if not test2_passed or not test3_passed or not test4_passed:
        print("ISSUE CONFIRMED: Heredoc commands have issues when sent to PTY.")
        print()
        print("This affects OpenHands SDK's SubprocessTerminal on macOS.")
        print("When the agent uses heredocs to create files, the commands time out.")
        print()
        print("Workarounds:")
        print("  1. Install tmux: brew install tmux")
        print("  2. Avoid heredocs in agent prompts")
        print()
        print("Proper fix: SubprocessTerminal should send multi-line commands")
        print("            line-by-line with small delays to mimic interactive input.")
        return 1
    else:
        print("All tests passed - heredocs work correctly on this system.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
