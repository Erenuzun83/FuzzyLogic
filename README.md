# FuzzyLogic
An adaptive Fuzzy Logic controller in Python with a PyQt6 GUI for real-time process control and self-tuning against disturbances. Communicates directly with Siemens PLCs via Snap7.

# Adaptive Fuzzy Logic Controller with Python

An intelligent, self-tuning process controller designed to handle real-world disturbances using Fuzzy Logic. This application provides a user-friendly graphical interface to configure, monitor, and adapt to industrial processes controlled by Siemens PLCs.

This project is the evolution of a previous MATLAB/OPC-based application, rebuilt in Python for greater flexibility, performance, and ease of deployment.

![Demo GIF/Screenshot](https://place-hold.it/800x450?text=Your-App-Screenshot-or-GIF-Here)
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
    git clone https://github.com/your-username/your-repo-name.git
    cd your-repo-name
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
