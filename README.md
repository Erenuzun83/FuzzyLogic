# FuzzyLogic
An adaptive Fuzzy Logic controller in Python with a PyQt6 GUI for real-time process control and self-tuning against disturbances. Communicates directly with Siemens PLCs via Snap7.

# Adaptive Fuzzy Logic Controller with Python

An intelligent, self-tuning process controller designed to handle real-world disturbances using Fuzzy Logic. This application provides a user-friendly graphical interface to configure, monitor, and adapt to industrial processes controlled by Siemens PLCs.

This project is the evolution of a previous MATLAB/OPC-based application, rebuilt in Python for greater flexibility, performance, and ease of deployment.
<img width="1020" height="1032" alt="vlcsnap-2025-11-17-09h03m10s643" src="https://github.com/user-attachments/assets/77351231-0ccb-4ca5-a36b-caa9f8f22f5c" />


*(Replace the placeholder above with a GIF or screenshot of your application in action!)*

## Key Features

-   **Intuitive Graphical User Interface (PyQt6):** Monitor real-time process data, adjust settings on the fly, and visualize fuzzy logic behavior.
-   **Interactive Fuzzy Logic Tuning:** Graphically adjust membership functions (aggressiveness, precision) and rules to define the controller's "expert knowledge."
-   **Self-Learning Adaptation to Disturbances:** The core of the project. The controller automatically detects unexpected process deviations and executes a multi-stage strategy (Observe -> Aggressive Correction -> Fine-Tune) to restore stability without human intervention.
-   **Direct Siemens PLC Communication (Snap7):** Bypasses the need for an OPC server, establishing a direct, low-latency connection to Siemens S7 PLCs for reading sensor data and writing outputs.
-   **Real-time Monitoring and Logging:** Track every decision and state change through a detailed log panel, providing full transparency into the controller's behavior.

## How the Adaptive Logic Works

Unlike a standard PID or a static fuzzy controller, this application shines when faced with unexpected events. When a major disturbance is detected:

1.  **Observe:** The controller pauses and intelligently observes how the system settles under the new, disturbed conditions with its standard fuzzy rules. This establishes a new baseline.
2.  **Aggressive Correction:** Based on the observed error, it calculates and applies a strong, decisive counter-action to rapidly push the process back towards the setpoint. Fuzzy control is temporarily suspended for this direct intervention.
3.  **Precision Observe:** As the error nears zero, the aggressive action is ceased, and the controller reverts to the safe baseline values to prevent overshoot. It then observes the system's response.
4.  **Fine-Tune & Lock:** Finally, it re-engages a refined fuzzy logic algorithm to eliminate any remaining small errors, learns the new stable state, and locks in the new optimal outputs.

## Technology Stack

-   **Backend & Logic:** Python
-   **GUI Framework:** PyQt6
-   **Fuzzy Logic Engine:** `scikit-fuzzy`
-   **PLC Communication:** `snap7`
-   **Data Handling & Computation:** NumPy
-   **Plotting:** Matplotlib

## Getting Started

### Prerequisites

-   Python 3.8+
-   A running Siemens S7 PLC instance (e.g., TIA Portal with PLCSIM Advanced or a physical PLC).
-   (Optional) Factory I/O for a full-scale process simulation.

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/Erenuzun83/FuzzyLogic.git
    cd FuzzyLogic
    ```
2.  Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

### Configuration

1.  Open the application.
2.  Enter your PLC's IP Address, Rack, and Slot in the **PLC Connection** panel.
3.  Configure the DB numbers and memory addresses for the setpoint, process variable, and valve outputs in the **PLC Addresses** panel.
4.  Adjust fuzzy rules, membership functions, and adaptation parameters as needed.
5.  Save your settings.

## Usage

1.  Click **"Connect to PLC"**.
2.  Once connected, click **"Start Control"** to activate the control loop.
3.  Monitor the process from the **System Status** and **Log** panels.
4.  Introduce a disturbance in your process (e.g., manually open a drain valve in Factory I/O) to see the adaptive logic in action.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

🚀 **Future Development & To-Do List**

This project is in active development. The goal is to evolve this controller into a more generic, powerful, and robust tool for various industrial automation challenges. Here is the planned roadmap:

**Phase 1: Generalization of Process Control (v2.0)**

Abstract Process Variables: Refactor the core logic to move beyond "level control." Introduce generic terms like "Process Variable (PV)" and "Setpoint (SP)" to make the controller adaptable for temperature, pressure, flow, etc.

Dynamic UI Configuration: Allow users to rename labels ("Tank Level", "Temperature") directly from the GUI, making the application instantly adaptable to different processes.

Scalable I/O Handling: Implement a more flexible system for defining inputs and outputs.

Allow users to add/remove more than two control elements (valves, heaters, pumps) dynamically.

Create a dedicated configuration panel to map each process element to its corresponding PLC address.

**Phase 2: Enhancement of Adaptive Logic (v2.1)**

Correction Logic Improvement: The AGGRESSIVE_CORRECTION phase is effective but can sometimes be too powerful. Research and implement alternative strategies:

Ramped Correction: Instead of a single, large step change, apply the correction over a short period (ramping) to reduce system shock.

Predictive Correction: Use the rate of change (delta) of the error during the OBSERVE phase to predict the required correction magnitude more accurately, instead of using a fixed multiplier.

Overshoot Suppression: Develop a smarter mechanism to prevent overshoot after AGGRESSIVE_CORRECTION. This could involve dynamically adjusting the proactive_reduction value based on the system's response speed.

**Phase 3: Usability and Deployment (v2.2)**

Configuration Profiles: Allow users to save and load different complete configurations (PLC settings, fuzzy rules, adaptation parameters) as named profiles.

Packaged Executable: Create a standalone executable file (using PyInstaller or similar tools) so that users can run the application without needing to install Python or any libraries.

Enhanced Plotting: Add a real-time trend chart to visualize the Process Variable (PV), Setpoint (SP), and valve outputs over time.


