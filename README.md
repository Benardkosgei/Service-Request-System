# Service Request System (SRS)

### Requirements
- Python 3.11 or later

### Tech Stack
- Frontend: HTML, CSS (Tailwind), JS (VanillaJS)
- Backend: Python (Flask)
- Database: MongoDB (pymongo driver)

### Instructions to setup the environment and run the application

1. Spawn a terminal session and go to root of the project's directory
    ```bash
    $ cd </path/to/project/directory>
    ```

2. Create a virtual environment
    ```bash
    $ python3 -m venv .
    ```

3. Activate the virtual environment

- In Unix-based systems (FreeBSD / Linux / MacOS)
    ```bash
    $ source bin/activate
    ```

- In Windows
    ```bash
    $ .\Scripts\activate.bat
    ```

4. Install dependencies using `requirements.txt`
   ```bash
   (service_request_system) $ python3 -m pip3 install requirements.txt
   ```

5. Change current working directory to `src/` and run the application
   ```bash
   (service_request_system) $ cd src/
   (service_request_system) $ python3 app.py
   ```

6. Finally, visit SRS portal at [http://127.0.0.1:5000/](http://127.0.0.1:5000/) using your browser (Chrome/Brave/Microsoft Edge/Firefox).

---
