# KoboBridge

KoboBridge is a Flask-based application designed to integrate data collected from the KoboToolbox platform with external event streaming services (such as Azure Event Hubs), enabling real-time forwarding and monitoring of survey submissions. The application also provides user authentication, system health monitoring, and configuration management.

## Key Features

- **KoboToolbox Integration**: 
  - Connects to the KoboToolbox API to fetch project metadata and form submissions.
  - Supports configuration of API credentials and polling intervals.
  - Provides endpoints to test API connection and list available KoboToolbox projects.

- **Real-Time Streaming**:
  - Submissions from KoboToolbox can be streamed in real-time to an external event streaming service, such as Azure Event Hubs.
  - Includes a background worker to poll KoboToolbox for new submissions and forward them to the event stream.
  - Tracks streaming status and logs events and metrics for each transmission.

- **Webhook Handling**:
  - Accepts POST requests with KoboToolbox data via a webhook endpoint.
  - Validates, processes, and forwards the data to the event streaming service.

- **User Authentication**:
  - User registration and login with password hashing.
  - Session management and user-specific configuration storage.
  - Uses Flask-Login for user session handling.

- **Monitoring and Health Checks**:
  - Provides endpoints to check system health, including event stream connectivity and recent errors.
  - Tracks and reports statistics such as success rates, average processing times, and recent log entries.

- **Configuration Management**:
  - Allows users to manage and update EventStream and KoboToolbox API configurations via dedicated endpoints.
  - Stores configuration both in user sessions and optionally in the database.

## Main Components

- `app.py`: Initializes the Flask application, configures logging, sets up extensions (database, login), and loads routes.
- `routes.py`: Defines the HTTP endpoints for webhooks, user auth, configuration, stats, and streaming controls.
- `kobo_client.py`: Implements the core logic for connecting to KoboToolbox, polling for projects and submissions, and streaming data to the event stream.
- `eventstream_client.py`: Handles the connection to the event streaming service, sending data, and reporting metrics and health status.
- `kobo_clientg.py`: Provides similar functionality to `kobo_client.py`, possibly as an alternative or generic implementation.
- `models.py`: Defines the database models for users, webhook logs, system health, and event stream metrics.

## Usage

The application is intended to be run as a Flask web service. Users interact with the API to configure bridge settings, authenticate, start/stop data streaming, and monitor system health. 

> **Note**: The application contains endpoints and configuration options related to external event streaming platforms and expects a valid KoboToolbox account and credentials for operation.

## Disclaimer

This documentation is based solely on the source code. If you need further details (such as deployment, environment setup, or advanced usage), refer to in-line code comments or seek additional documentation.
