Employee Presence Monitoring System
This repository contains the implementation of a web-based system for analyzing employee presence at workplaces using a neural network approach, developed as part of a coursework project at South Ural State University (SUSU), Department of System Programming.
Project Overview
The system automates monitoring of employee presence in office environments by processing video streams from cameras. It leverages computer vision techniques to detect and track employees, register workplaces based on temporal criteria, and generate occupancy reports. The project was developed to meet modern requirements for informational systems in educational institutions and is applicable for administrative tasks at SUSU.
Objectives

Develop a system for real-time employee presence analysis.
Implement object detection using YOLOv11l and tracking with DeepSORT.
Create a user-friendly web interface for video stream visualization, workplace management, and report generation.
Ensure system scalability and performance for multiple video streams.

Key Features

Video Stream Processing: Captures and displays video with overlaid bounding boxes for detected employees and registered workplaces.
Employee Detection and Tracking: Uses YOLOv11l for detecting people and DeepSORT for assigning unique IDs and tracking movements.
Workplace Registration: Automatically identifies potential workplaces when an employee remains in an area for a specified time (e.g., 5 minutes).
User Interface: Provides a web-based interface for starting video streams, confirming or deleting workplaces, adjusting parameters, and viewing occupancy reports.
Notifications: Alerts users about new potential workplaces via the interface.
Reports: Generates textual and graphical reports on workplace occupancy.

Technologies Used

Backend: Python 3.12, Django, Django Channels, SQLite
Computer Vision: Ultralytics YOLOv11l (pre-trained on COCO dataset), DeepSORT, OpenCV
Frontend: HTML, CSS, JavaScript, Chart.js
Development Environment: Visual Studio Code
Dependencies: Managed via requirements.txt

System Architecture
The system employs a client-server architecture:

Backend: Handles video processing, database operations, REST API, and WebSocket connections for real-time video streaming.
Frontend: Renders the user interface, displays video streams, and interacts with the backend via API and WebSocket.
Database: SQLite stores workplace data, including coordinates and occupancy history.

See the architecture diagram for details (refer to image7.png in the coursework).
Installation
Prerequisites

Python 3.12
Git
NVIDIA GPU (recommended for YOLOv11l performance)
CUDA and cuDNN (if using GPU)

Steps

Clone the repository:git clone https://github.com/your-username/employee-presence-monitoring.git
cd employee-presence-monitoring


Create and activate a virtual environment:python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate


Install dependencies:pip install -r requirements.txt


Install YOLOv11l weights:
Download pre-trained weights from Ultralytics YOLOv11 and place them in the models/ directory.


Set up SQLite database:python manage.py migrate


Run the Django server:python manage.py runserver



Configuration

Update settings.py for video source (e.g., IP camera URL or local video file).
Adjust detection thresholds and workplace registration time in tracker/video_processing.py.

Usage

Access the web interface at http://localhost:8000.
Enter a video source (e.g., webcam index or video file URL) and click "Start".
Monitor the video stream with overlaid employee IDs and workplace boundaries.
Confirm or reject new workplace suggestions via notifications.
Generate occupancy reports for registered workplaces.

Testing Results

Functional Testing: 10 tests passed, covering video processing, detection, tracking, workplace management, and report generation.
Performance Testing: Achieved 50 FPS on a single stream, supporting up to 5 concurrent streams (AMD Ryzen 7 5800H, NVIDIA RTX 3070).
Usability Testing: Identified and fixed 4 issues (e.g., URL field hints, button visibility, deletion confirmation, report visualization).
Interface Testing: Confirmed cross-browser compatibility (Chrome, Firefox, Edge) and adaptability across resolutions (2560x1440 to 768x1024).

Future Improvements

Fine-tune YOLOv11l on custom datasets for improved accuracy in specific environments.
Optimize performance for handling more video streams.
Enhance report visualization with advanced charts (e.g., time-series occupancy graphs).

Documentation

Coursework Document: Detailed description of analysis, design, implementation, and testing.
Presentation: Slides covering project overview, architecture, and results.

References

Ultralytics YOLOv11 Documentation: https://docs.ultralytics.com/
DeepSORT Repository: https://github.com/nwojke/deep_sort
COCO Dataset: https://cocodataset.org/

License
This project is licensed under the MIT License. See LICENSE for details.
Acknowledgments

South Ural State University, Department of System Programming
Supervisor: N. S. Silkina
