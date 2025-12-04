# 🌍 Open Energy Backend — FastAPI Service
### Electricity Production Mix API (Israel NOGA Integration)

This backend application fetches, processes, and provides real-time and historical data about Israel’s electricity production mix. It is an API (Application Programming Interface), which means it provides data to other applications.

---

## 🚀 Key Features

*   **Real-time Data:** Fetches the most up-to-date electricity production data.
*   **Historical Data:** Access historical data for different time periods.
*   **Data Aggregation:** Summarizes the data into easy-to-understand categories.
*   **Export Data:** Allows you to download the data in CSV or Excel formats.

---

## 🏁 Getting Started

Follow these steps to get the application running on your computer.

### 1. Prerequisites

Before you start, make sure you have the following software installed on your computer:

*   **Python:** A programming language needed to run the application. You can download it from [python.org](https://www.python.org/downloads/).

### 2. Setup

This will guide you through setting up the project on your computer.

**a. Open a Terminal (Command Prompt)**

*   **Windows:** Press the `Windows Key`, type `cmd`, and press `Enter`.
*   **macOS:** Open `Finder`, go to `Applications` -> `Utilities`, and open `Terminal`.
*   **Linux:** Usually `Ctrl+Alt+T` opens the terminal.

**b. Create a Virtual Environment**

This creates an isolated environment for the project's dependencies. Make sure you are in the project's root directory.

```bash
python -m venv venv
```

**c. Activate the Virtual Environment**

*   **Windows:**
    ```bash
    venv\Scripts\activate
    ```
*   **macOS and Linux:**
    ```bash
    source venv/bin/activate
    ```
    Your terminal prompt should now have `(venv)` at the beginning.

**d. Install the Required Packages**

This will install all the necessary libraries for the project.

```bash
pip install -r requirements.txt
```

### 3. Run the Application

Now that the setup is complete, you can start the application.

```bash
uvicorn app.main:app --reload
```

You should see a message indicating that the application is running, like this:
`INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)`

This means your API is running and ready to be used!

---

## 📡 How to Use the API

The application provides several URLs (we call them "endpoints") that you can access to get data. You can test these endpoints in two main ways:

### 1. Interactive API Documentation (Recommended)

The easiest way to explore and test the API is by using the built-in documentation. Once the application is running, open one of the following links in your web browser:

*   **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
*   **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

These interfaces allow you to see all the available endpoints and try them out directly from your browser.

### 2. Using an API Client (like Postman)

For more advanced testing, you can use an API client like [Postman](https://www.postman.com/downloads/). You can copy and paste the URLs from the list below into Postman to test them.

---

## 📋 List of API Endpoints

Here are some of the main endpoints you can use. You can specify a date range by adding `start_date` and `end_date` to the URL.

*   **Get Production Mix**
    *   `http://127.0.0.1:8000/api/v1/energy/production-mix?start_date=2023-01-01&end_date=2023-12-31`

*   **Export Production Mix to CSV**
    *   `http://127.0.0.1:8000/api/v1/energy/production-mix/export?start_date=2023-01-01&end_date=2023-12-31`

*   **Get Energy Overview**
    *   `http://127.0.0.1:8000/api/v1/energy/overview?start_date=2023-01-01&end_date=2023-12-31`

*   **Get Energy Overview Details**
    *   `http://127.0.0.1:8000/api/v1/energy/overview/details?start_date=2023-01-01&end_date=2023-12-31`

*   **Export Energy Overview to Excel**
    *   `http://127.0.0.1:8000/api/v1/energy/overview/export?start_date=2023-01-01&end_date=2023-12-31`

*   **Get SMP Data**
    *   `http://127.0.0.1:8000/api/v1/energy/smp/?start_date=2023-01-01&end_date=2023-12-31`

*   **Get SMP Production vs Marginal Price**
    *   `http://127.0.0.1:8000/api/v1/energy/smp-production-vs-marginal-price/?start_date=2023-01-01&end_date=2023-01-31`

*   **Get Private supplier**
    *   'http://127.0.0.1:8000/api/v1/private-supplier-connected-consumers/?start_date=10-2022&end_date=11-2023'



