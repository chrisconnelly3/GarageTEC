==========================================================================
 Golf Shot Capture - SPIKE  (read me first)
==========================================================================

WHAT THIS IS
A little app that listens to a Garmin Approach R50 and shows each shot as you
hit it. We use it to confirm we can capture the R50's shot data. The app walks
you through everything on screen - this page is just a backup.

WHAT TO COPY TO THE LAPTOP
ON A WINDOWS PC - just two files:
    R50_Spike_Listener.exe
    README_SPIKE.txt   (this file)
No install, no Python. Put them in any folder (e.g. the Desktop).
The shot log is saved right next to the .exe.

ON A MAC - the .exe does NOT work on a Mac (it's Windows-only). Use the Python
version instead (see the "ON A MAC" section below). Copy these files:
    gspro_spike_listener.py
    Start Spike Listener.command
    README_SPIKE.txt   (this file)

==========================================================================
 HOW TO RUN IT
==========================================================================
1. Double-click  R50_Spike_Listener.exe

2. If Windows shows a blue "Windows protected your PC" box:
      - click "More info"  ->  "Run anyway"   (the file just isn't signed)

3. If Windows asks to ALLOW the app on your network:
      - click "Allow access" / "Yes"

4. Now just FOLLOW THE STEPS ON SCREEN. In short:
      Step 1 - On the R50: tap Connect, then GSPro (it shows a Wi-Fi name + password).
      Step 2 - On the laptop: click the Wi-Fi icon (bottom-right), join that R50
               Wi-Fi using the password from the R50 screen.
      Step 3 - The R50 connects on its own, then you take a swing. Shots pop up.

   The app shows green when it's connected, and shows each shot as you hit it.
   You do NOT need to press Start or type anything - it runs itself.

==========================================================================
 ON A MAC  (no .exe - run the Python version)
==========================================================================
The app itself is cross-platform; only the .exe is Windows-only. On a Mac you
run the same app through Python (a one-time install).

1. Install Python 3:
     - Go to  https://www.python.org/downloads/macos/
     - Download the latest macOS installer and run it (use the python.org build
       - it includes "Tkinter", which the app's window needs; the Homebrew one
       may not).
2. Put these two files in a folder (e.g. the Desktop):
       gspro_spike_listener.py
       Start Spike Listener.command
3. Double-click  "Start Spike Listener.command"
     - First time, macOS may say it's from an "unidentified developer":
         right-click (or Control-click) the file -> Open -> Open.
     - If it says "permission denied" or won't open: open the Terminal app, type
         chmod +x        (with a space after it), then DRAG the .command file
       into the Terminal window and press Return. Now double-click it again.
     - Simplest fallback: open Terminal, type   python3   and a space, then DRAG
       gspro_spike_listener.py into the window and press Return.
4. If macOS asks to ALLOW incoming network connections, click "Allow."
5. Join the R50's Wi-Fi from the Wi-Fi menu in the TOP-right menu bar, then
   follow the same on-screen steps. Shots pop up as you hit them.

(Everything else - the steps, the green "connected" light, the saved log file -
works exactly the same as on Windows.)

==========================================================================
 WHEN YOU'RE DONE - SEND THIS BACK
==========================================================================
- In the app, click  "All done - get the file to send"  (opens the folder).
- Send back the file named   spike_log_<date>.jsonl
- Also mention: did shots appear, and did it say club data was "included" or
  "ball only"?

==========================================================================
 IF IT GETS STUCK
==========================================================================
- "Waiting for your R50..." forever:
     make sure the laptop is on the R50's Wi-Fi (Step 2), not the house Wi-Fi.
     Give the R50 ~20 seconds after Step 2. If the R50 asks for an "address",
     type the address the app shows on Step 2/3, and the port 921.
- "Needs attention / port in use":
     another golf app (like GSPro) is already open. Fully close it, then click
     "Try again" in the app.
- There's a "Help" button inside the app with these same tips.

==========================================================================
 PLAN B  (only if the .exe will not run / antivirus blocks it)
==========================================================================
1. Install Python from https://www.python.org/downloads/
   (tick "Add python.exe to PATH" on the first screen).
2. Put gspro_spike_listener.py and "Start Spike Listener.bat" in a folder.
3. Double-click "Start Spike Listener.bat", then follow the on-screen steps.
==========================================================================
