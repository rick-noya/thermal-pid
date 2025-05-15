import os
import sys
import logging
import traceback
import datetime
import tempfile
import platform
import json
import io
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from contextlib import contextmanager

# Configure module logger
logger = logging.getLogger("thermal-pid.crash_reporter")

class CrashReporter:
    """
    Advanced crash reporting system for the Thermal PID application.
    Handles logging exceptions, generating crash reports, and facilitating user feedback.
    """
    
    def __init__(self, app_version="1.0.0", logs_dir="logs", report_url=None):
        """
        Initialize the crash reporter.
        
        Args:
            app_version: The application version
            logs_dir: Directory where logs and crash reports will be stored
            report_url: URL for submitting crash reports (if implemented)
        """
        self.app_version = app_version
        self.logs_dir = logs_dir
        self.report_url = report_url
        self.app_state = {}
        
        # Create logs directory if needed
        os.makedirs(logs_dir, exist_ok=True)
    
    def capture_app_state(self, **kwargs):
        """
        Capture the current application state for crash reporting.
        This method can be called periodically to store the latest state.
        
        Args:
            **kwargs: Key-value pairs representing application state
        """
        self.app_state.update(kwargs)
    
    def clear_app_state(self):
        """Clear the captured application state."""
        self.app_state.clear()
    
    def take_screenshot(self, widget=None):
        """
        Take a screenshot of the application window for crash reporting.
        
        Args:
            widget: The tkinter widget to capture (root window if None)
            
        Returns:
            Path to the screenshot file or None if screenshot failed
        """
        try:
            if not widget:
                # Try to find the root window
                for w in tk._default_root.winfo_children():
                    if isinstance(w, tk.Toplevel):
                        widget = w
                        break
                else:
                    widget = tk._default_root
            
            # Ensure PIL is available
            from PIL import ImageGrab
            
            # Get widget geometry
            widget.update_idletasks()
            x, y = widget.winfo_rootx(), widget.winfo_rooty()
            width, height = widget.winfo_width(), widget.winfo_height()
            
            # Take the screenshot
            screenshot = ImageGrab.grab(bbox=(x, y, x+width, y+height))
            
            # Save to file
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_path = os.path.join(self.logs_dir, f"crash_screenshot_{timestamp}.png")
            screenshot.save(screenshot_path)
            
            return screenshot_path
        except Exception as e:
            logger.warning(f"Failed to take screenshot: {e}")
            return None
    
    def handle_exception(self, exc_type, exc_value, exc_traceback, app_context=None, prompt_user=True):
        """
        Handle an exception by generating a crash report and optionally prompting the user.
        
        Args:
            exc_type: The exception type
            exc_value: The exception value
            exc_traceback: The exception traceback
            app_context: Additional application context to include in the report
            prompt_user: Whether to show a dialog to the user
            
        Returns:
            Path to the crash report file
        """
        try:
            # Log the full exception with traceback
            logger.critical("Uncaught exception", 
                           exc_info=(exc_type, exc_value, exc_traceback))
            
            # Generate crash report filename
            crash_time = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            crash_report_path = os.path.join(self.logs_dir, f"crash_report_{crash_time}.txt")
            
            # Take screenshot if possible
            screenshot_path = self.take_screenshot() if 'PIL' in sys.modules else None
            
            # Write the crash report
            with open(crash_report_path, 'w') as f:
                # System information
                f.write(f"=== Thermal PID Crash Report - {crash_time} ===\n\n")
                f.write(f"Application Version: {self.app_version}\n")
                f.write(f"Python Version: {platform.python_version()}\n")
                f.write(f"OS: {platform.system()} {platform.release()} {platform.version()}\n")
                f.write(f"Platform: {platform.platform()}\n")
                
                if screenshot_path:
                    f.write(f"Screenshot: {screenshot_path}\n")
                
                f.write("\n")
                
                # Exception information
                f.write(f"Exception Type: {exc_type.__name__}\n")
                f.write(f"Exception Message: {exc_value}\n\n")
                f.write("Traceback:\n")
                f.write(''.join(traceback.format_tb(exc_traceback)))
                
                # App state information if available
                if self.app_state:
                    f.write("\nApplication State:\n")
                    try:
                        app_state_str = json.dumps(self.app_state, indent=2, default=str)
                        f.write(app_state_str)
                    except Exception as json_err:
                        f.write(f"Error serializing app state: {json_err}\n")
                        f.write(str(self.app_state))
                
                # Additional context provided for this specific crash
                if app_context:
                    f.write("\nAdditional Context:\n")
                    for key, value in app_context.items():
                        f.write(f"{key}: {value}\n")
                
                # Get some additional context if available
                try:
                    if isinstance(exc_value, ModuleNotFoundError):
                        f.write(f"\nA required module was not found: {exc_value.name}. "
                                f"Try running 'pip install {exc_value.name}'.\n")
                    elif isinstance(exc_value, PermissionError):
                        f.write("\nPermission denied. Check if the program has necessary permissions.\n")
                    elif isinstance(exc_value, FileNotFoundError):
                        f.write(f"\nA file was not found: {exc_value.filename}\n")
                except:
                    pass
                
                # Include the last 100 lines from the log file if available
                log_files = [f for f in os.listdir(self.logs_dir) if f.startswith("thermal_pid_") and f.endswith(".log")]
                if log_files:
                    latest_log = os.path.join(self.logs_dir, sorted(log_files)[-1])
                    f.write("\nRecent Log Entries:\n")
                    try:
                        with open(latest_log, 'r') as log_file:
                            log_lines = log_file.readlines()
                            f.write(''.join(log_lines[-100:]))  # Last 100 lines
                    except Exception as log_err:
                        f.write(f"Error reading log file: {log_err}\n")
            
            # Prompt the user if requested
            if prompt_user:
                self._show_crash_dialog(exc_type, exc_value, crash_report_path)
            
            return crash_report_path
            
        except Exception as report_err:
            # If there's an error during crash reporting, log it and fall back to simpler reporting
            logger.error(f"Error in crash reporter: {report_err}")
            backup_path = os.path.join(self.logs_dir, f"crash_backup_{crash_time}.txt")
            try:
                with open(backup_path, 'w') as backup_file:
                    backup_file.write(f"Error in crash reporter: {report_err}\n\n")
                    backup_file.write(f"Original exception: {exc_type.__name__}: {exc_value}\n")
                    backup_file.write(''.join(traceback.format_tb(exc_traceback)))
                return backup_path
            except:
                logger.critical("Complete failure of crash reporting system", exc_info=True)
                return None
    
    def _show_crash_dialog(self, exc_type, exc_value, crash_report_path):
        """Show error dialog to the user with crash information."""
        try:
            # Ensure we're not creating a new main window if one exists
            root = tk._default_root or tk.Tk()
            
            if not tk._default_root:
                root.withdraw()  # Hide the window if we created it
            
            messagebox.showerror(
                "Application Error",
                f"The application encountered an unexpected error and needs to close.\n\n"
                f"Error: {exc_type.__name__}: {exc_value}\n\n"
                f"A crash report has been saved to:\n{crash_report_path}\n\n"
                f"Please report this issue with the crash report file."
            )
            
            if not tk._default_root:
                root.destroy()
                
        except Exception as dialog_err:
            # If showing the messagebox fails, at least print to console
            logger.error(f"Failed to show crash dialog: {dialog_err}")
            print(f"Critical error: {exc_type.__name__}: {exc_value}")
            print(f"Crash report has been saved to: {crash_report_path}")
    
    def install_global_handler(self):
        """Install the crash reporter as the global exception handler."""
        def global_exception_handler(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                # Don't capture keyboard interrupt (Ctrl+C)
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            
            self.handle_exception(exc_type, exc_value, exc_traceback)
            sys.exit(1)  # Exit the application after crash reporting
        
        sys.excepthook = global_exception_handler

    @contextmanager
    def error_context(self, context_info=None, exit_on_exception=False):
        """
        Context manager to automatically handle exceptions with additional context.
        
        Usage:
            with crash_reporter.error_context({"operation": "saving_file"}):
                # code that might raise an exception
        
        Args:
            context_info: Dictionary of additional context information
            exit_on_exception: Whether to exit the application after handling the exception
        """
        try:
            yield
        except Exception as e:
            exc_type, exc_value, exc_tb = sys.exc_info()
            self.handle_exception(exc_type, exc_value, exc_tb, app_context=context_info)
            if exit_on_exception:
                sys.exit(1)
            else:
                raise  # Re-raise the exception for higher-level handlers

# Create a global instance for easy importing throughout the application
crash_reporter = CrashReporter()

# Helper function to install the global handler
def install_global_handler():
    """Install the crash reporter as the global exception handler."""
    crash_reporter.install_global_handler() 