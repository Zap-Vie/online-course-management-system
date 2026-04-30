# Online Course Management System

A robust, database-driven web application designed to efficiently manage online courses, instructors, learners, and enrollments. This project was developed as part of the Database Systems course at the National Economics University (NEU) - Faculty of Data Science and Artificial Intelligence.

## Features

### 1. User Roles & Authentication
* **Manager:** Full administrative access to manage instructors, courses, learners, and view system statistics.
* **Instructor:** Can view assigned courses and manage lecture materials.
* **Learner:** Can view available courses, enroll in classes, and track learning progress.
* **Security:** Secure login system with hashed passwords and role-based session management.

### 2. Core Management Modules (CRUD)
* **Instructor Management:** Register, update, and remove instructor profiles.
* **Course Management:** Create courses, assign instructors, and update course details.
* **Learner Management:** Register learners and manage their personal information.
* **Enrollment Management:** Track which learners are enrolled in which courses.

### 3. Advanced Database Features
The underlying MySQL database is optimized with advanced relational database concepts:
* **Indexes:** Optimized query performance for course searches and enrollment tracking.
* **Views:** Custom views (v_instructor_load) to quickly aggregate instructor teaching loads and learner course counts.
* **Stored Procedures:** Automated and safe transaction handling for course enrollment counts (sp_course_summary).
* **Triggers & Audit Logging:** Automated triggers on INSERT, UPDATE, and DELETE actions across all main tables to maintain a strict system AuditLog.

## Tech Stack

* **Backend:** Python, Flask Framework
* **Database:** MySQL (connected via mysql-connector-python)
* **Frontend:** HTML5, CSS3, JavaScript (Vanilla JS), Chart.js (for statistical visualizations)

## Installation & Setup

Follow these steps to run the project locally on your machine.

### Prerequisites
* Python 3.8+
* MySQL Server (XAMPP, MySQL Workbench, or standalone)
* Git

### 1. Clone the repository
```bash
git clone [https://github.com/Zap-Vie/online-course-management-system.git](https://github.com/Zap-Vie/online-course-management-system.git)
cd online-course-management-system
```

### 2. Install required Python packages
Create a virtual environment (optional but recommended) and install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Ensure your local MySQL server is running. Then, configure your database connection credentials (e.g., in your `.env` file or configuration module) to match your local environment:
```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=online_course_db
SECRET_KEY=your_flask_secretkey
MYSQLDUMP_PATH=SQLDUMP.exe path
```

### 4. Run the Application
Start the Flask development server:
```bash
python app.py
```
The application will be running at http://127.0.0.1:5000/.

## Author

**Giáp Trần Quang Vinh**
* **Major:** Data Science
* **Institution:** National Economics University (NEU)

## License
This project is for educational purposes as part of the university curriculum.
