import serial.tools.list_ports
import sys
import os
import time

# Add parent directory to sys.path to allow importing from devices
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from devices.camera import SenxorCamera
    # Further imports if SenxorCamera or its dependencies need them explicitly for this script
    from devices.signal_generator import SignalGenerator
except ImportError as e:
    print(f"Error importing SenxorCamera or SignalGenerator: {e}")
    print("Please ensure that the script is in the project's root directory or adjust the PYTHONPATH.")
    sys.exit(1)

def query_all_ports():
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No COM ports found.")
        return

    print("Scanning COM ports for Senxor/MI48 cameras...")
    camera_mappings = {}

    for port_info in ports:
        port_name = port_info.device
        print(f"\nAttempting to connect to camera on port: {port_name}")
        
        camera = None
        try:
            # Initialize SenxorCamera. It attempts to connect and configure.
            # We don't need to start streaming for just getting the ID.
            camera = SenxorCamera(port=port_name)

            if camera.is_connected and camera.mi48:
                # The get_camera_info() method populates camera_id, camera_id_hexsn, sn etc.
                # We need to ensure get_camera_info() is called if it's not called by __init__ implicitly.
                # SenxorCamera.__init__ calls _connect(), which calls connect_senxor(),
                # which initializes MI48, and MI48.__init__ calls get_camera_info().
                # So the info should be available.
                
                camera_id_hexsn = getattr(camera.mi48, 'camera_id_hexsn', None)
                camera_sn_attr = getattr(camera.mi48, 'sn', None)

                if camera_id_hexsn:
                    print(f"  Successfully connected to camera on {port_name}")
                    print(f"  Camera ID (Year.Week.Fab.SerNumHex): {camera_id_hexsn}")
                    if camera_sn_attr:
                         print(f"  Camera SN (SN+HexID): {camera_sn_attr}")
                    camera_mappings[port_name] = camera_id_hexsn
                elif camera_sn_attr: # Fallback if camera_id_hexsn is not there for some reason
                    print(f"  Successfully connected to camera on {port_name}")
                    print(f"  Camera SN (SN+HexID): {camera_sn_attr}")
                    camera_mappings[port_name] = camera_sn_attr
                else:
                    print(f"  Connected to {port_name}, but could not retrieve a serial number.")
            else:
                print(f"  Could not establish a full connection to a Senxor/MI48 camera on {port_name}.")

        except Exception as e:
            print(f"  Error connecting to or querying camera on {port_name}: {e}")
        finally:
            if camera and camera.is_connected:
                try:
                    # SenxorCamera.stop() calls mi48.stop() which closes interfaces
                    camera.stop() 
                    print(f"  Closed connection to {port_name}")
                except Exception as e:
                    print(f"  Error closing camera on {port_name}: {e}")
            elif camera: # If camera object exists but wasn't fully connected/mi48 object not there
                if camera.mi48: # if mi48 object exists, try to call its stop method.
                    try:
                        camera.mi48.stop()
                        print(f"  Closed MI48 interface for {port_name}")
                    except Exception as e:
                         print(f"  Error closing MI48 interface for {port_name}: {e}")


    if camera_mappings:
        print("\n--- Camera to COM Port Mappings ---")
        for port, sn_id in camera_mappings.items():
            print(f"  {port}: {sn_id}")
        print("-----------------------------------")
    else:
        print("\nNo Senxor/MI48 cameras with identifiable serial numbers found.")

    # --- ESP32 Display Detection ---
    print("\nScanning COM ports for ESP32 display devices...")
    esp32_ports = []
    for port_info in ports:
        desc = (port_info.description or '').lower()
        manu = (port_info.manufacturer or '').lower()
        if (
            'cp210' in desc or 'cp210' in manu or
            'ch340' in desc or 'ch340' in manu or
            'ftdi' in desc or 'ftdi' in manu or
            'usb serial' in desc or 'usb-serial' in desc or
            'esp32' in desc or 'esp32' in manu
        ):
            try:
                with serial.Serial(port_info.device, 115200, timeout=2) as ser:
                    # Opening the serial port on ESP32 usually toggles DTR and resets the board.
                    # Give the microcontroller time to (re)boot and print its banner/ID.
                    time.sleep(2)  # wait for boot messages

                    lines = []
                    # Read any lines already waiting in the buffer (e.g., ID sent at startup)
                    while ser.in_waiting:
                        try:
                            raw = ser.readline()
                            decoded = raw.decode("utf-8", errors="ignore").strip()
                            if decoded:
                                lines.append(decoded)
                        except Exception:
                            break

                    # Look for an ID in the lines we just captured.
                    esp32_id = None
                    for ln in lines:
                        if ln.startswith("ID:"):
                            esp32_id = ln.split(":", 1)[1]
                            break

                    # If we didn't see it, explicitly request it.
                    if esp32_id is None:
                        ser.write(b"ID?\n")
                        # Give the ESP32 a moment to respond
                        time.sleep(0.5)
                        resp = ser.readline().decode("utf-8", errors="ignore").strip()
                        if resp.startswith("ID:"):
                            esp32_id = resp.split(":", 1)[1]

                    if esp32_id:
                        print(f"  ESP32 Display detected on {port_info.device}: {esp32_id}")
                        esp32_ports.append((port_info.device, esp32_id))
            except Exception as e:
                print(f"  Error querying ESP32 on {port_info.device}: {e}")
    if esp32_ports:
        print("\n--- ESP32 Display COM Ports Detected ---")
        for device, esp32_id in esp32_ports:
            print(f"  {device}: {esp32_id}")
        print("----------------------------------------")
    else:
        print("No ESP32 display devices detected on any COM port.")

    # --- Signal Generator Detection ---
    print("\nScanning COM ports for Signal Generators...")
    siggen_ports = []
    for port_info in ports:
        port_name = port_info.device
        siggen = None
        try:
            siggen = SignalGenerator(port=port_name)
            siggen.open()
            siggen_id = siggen.get_id()
            if siggen_id:
                print(f"  Signal Generator detected on {port_name}: {siggen_id}")
                siggen_ports.append((port_name, siggen_id))
            siggen.close()
        except Exception as e:
            # Only print if a partial connection was made
            if siggen and getattr(siggen, 'is_open', False):
                print(f"  Error querying Signal Generator on {port_name}: {e}")
                try:
                    siggen.close()
                except Exception:
                    pass
    if siggen_ports:
        print("\n--- Signal Generator COM Ports Detected ---")
        for port, sg_id in siggen_ports:
            print(f"  {port}: {sg_id}")
        print("------------------------------------------")
    else:
        print("No Signal Generators detected on any COM port.")

if __name__ == "__main__":
    # This is to ensure that if main.py (or other scripts) use 'if __name__ == "__main__"'
    # their code doesn't run when this script imports them.
    # However, SenxorCamera and its dependencies might print info during initialization.
    
    # It's better if the underlying libraries (MI48, SenxorCamera)
    # use proper logging instead of print statements for non-essential info,
    # or provide a quiet mode for library use.
    # For now, we'll proceed.
    
    query_all_ports() 