import os
import datetime
from dotenv import load_dotenv
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

# --- Configuration ---
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

def get_base_connection():
    """Connects to MySQL server without selecting a specific database."""
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD
    )

def get_db_connection():
    """Connects directly to the initialized application database."""
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

def initialize_database():
    """Executes schema and advanced object creation if they do not exist."""
    conn = get_base_connection()
    cursor = conn.cursor()

    # 1. Create Database
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cursor.execute(f"USE {DB_NAME}")

    # 2. Create Tables
    tables = {}
    tables['Learners'] = (
        "CREATE TABLE IF NOT EXISTS Learners ("
        "  LearnerID INT PRIMARY KEY,"
        "  LearnerName VARCHAR(255) NOT NULL,"
        "  Email VARCHAR(255) UNIQUE,"
        "  PhoneNumber VARCHAR(20)"
        ")"
    )
    tables['Instructors'] = (
        "CREATE TABLE IF NOT EXISTS Instructors ("
        "  InstructorID INT PRIMARY KEY,"
        "  InstructorName VARCHAR(255) NOT NULL,"
        "  Expertise VARCHAR(255),"
        "  Email VARCHAR(255) UNIQUE"
        ")"
    )
    tables['Account'] = (
        "CREATE TABLE IF NOT EXISTS Account ("
        "  Email VARCHAR(255) PRIMARY KEY,"
        "  Password VARCHAR(255) NOT NULL,"
        "  Role TINYINT NOT NULL"
        ")"
    )
    tables['Courses'] = (
        "CREATE TABLE IF NOT EXISTS Courses ("
        "  CourseID INT AUTO_INCREMENT PRIMARY KEY,"
        "  CourseName VARCHAR(255) NOT NULL,"
        "  Description TEXT,"
        "  InstructorID INT,"
        "  FOREIGN KEY (InstructorID) REFERENCES Instructors(InstructorID)"
        ")"
    )
    tables['Lectures'] = (
        "CREATE TABLE IF NOT EXISTS Lectures ("
        "  LectureID INT AUTO_INCREMENT,"
        "  CourseID INT NOT NULL,"
        "  Title VARCHAR(255) NOT NULL,"
        "  Content TEXT,"
        "  PRIMARY KEY (CourseID, LectureID),"
        "  KEY (LectureID)," 
        "  FOREIGN KEY (CourseID) REFERENCES Courses(CourseID)"
        ")"
    )
    tables['Enrollments'] = (
        "CREATE TABLE IF NOT EXISTS Enrollments ("
        "  EnrollmentID INT AUTO_INCREMENT PRIMARY KEY,"
        "  LearnerID INT,"
        "  CourseID INT,"
        "  EnrollmentDate DATETIME DEFAULT CURRENT_TIMESTAMP,"
        "  FOREIGN KEY (LearnerID) REFERENCES Learners(LearnerID),"
        "  FOREIGN KEY (CourseID) REFERENCES Courses(CourseID)"
        ")"
    )
    tables['AuditLog'] = (
        "CREATE TABLE IF NOT EXISTS AuditLog ("
        "  AuditID INT AUTO_INCREMENT PRIMARY KEY,"
        "  ActionText TEXT,"
        "  ActionTime DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")"
    )

    for table_name in tables:
        cursor.execute(tables[table_name])

    # 3. Create Views
    cursor.execute("DROP VIEW IF EXISTS v_instructor_load")
    cursor.execute("""
        CREATE VIEW v_instructor_load AS 
        SELECT i.InstructorID, i.InstructorName, COUNT(c.CourseID) AS TotalCourses 
        FROM Instructors i 
        LEFT JOIN Courses c ON i.InstructorID = c.InstructorID 
        GROUP BY i.InstructorID, i.InstructorName
    """)
    cursor.execute("DROP VIEW IF EXISTS v_enrollment_trend")
    cursor.execute("""
        CREATE VIEW v_enrollment_trend AS
        SELECT DATE_FORMAT(e.EnrollmentDate, '%Y-%m') AS Month,
        c.CourseID,
        c.CourseName,
        COUNT(e.EnrollmentID) AS LearnerCount
        FROM Enrollments e
        JOIN Courses c ON e.CourseID = c.CourseID
        GROUP BY DATE_FORMAT(e.EnrollmentDate, '%Y-%m'), c.CourseID, c.CourseName
        ORDER BY Month;"""
    )
    # 4. Create Stored Procedures
    cursor.execute("DROP PROCEDURE IF EXISTS sp_course_summary")
    cursor.execute("""
        CREATE PROCEDURE sp_course_summary(IN p_course_id INT)
        BEGIN
            SELECT c.CourseName, 
                   COUNT(e.EnrollmentID) AS TotalLearners  
            FROM Courses c 
            LEFT JOIN Enrollments e ON c.CourseID = e.CourseID 
            WHERE c.CourseID = p_course_id 
            GROUP BY c.CourseID;
        END
    """)
    cursor.execute("DROP PROCEDURE IF EXISTS sp_system_statistics")
    cursor.execute("""
        CREATE PROCEDURE sp_system_statistics()
        BEGIN
            SELECT COUNT(*) AS total_courses FROM Courses;
            SELECT COUNT(*) AS total_learners FROM Learners;
            SELECT * FROM v_instructor_load ORDER BY TotalCourses DESC;
            SELECT * FROM v_enrollment_trend;
        END
    """)
    # 5. Create Triggers
    cursor.execute("DROP TRIGGER IF EXISTS trg_after_enrollment")
    cursor.execute("""
        CREATE TRIGGER trg_after_enrollment 
        AFTER INSERT ON Enrollments 
        FOR EACH ROW 
        BEGIN
            INSERT INTO AuditLog (ActionText) 
            VALUES (CONCAT('Learner ', NEW.LearnerID, ' enrolled in Course ', NEW.CourseID));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_after_enrollment_update")
    cursor.execute("""
        CREATE TRIGGER trg_after_enrollment_update 
        AFTER UPDATE ON Enrollments 
        FOR EACH ROW 
        BEGIN
            INSERT INTO AuditLog (ActionText) 
            VALUES (CONCAT('Enrollment ', NEW.EnrollmentID, ' updated: Learner ', NEW.LearnerID, ' changed Course from ', OLD.CourseID, ' to ', NEW.CourseID));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_after_enrollment_delete")
    cursor.execute("""
        CREATE TRIGGER trg_after_enrollment_delete 
        AFTER DELETE ON Enrollments 
        FOR EACH ROW 
        BEGIN
            INSERT INTO AuditLog (ActionText) 
            VALUES (CONCAT('Learner ', OLD.LearnerID, ' dropped Course ', OLD.CourseID));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_learner_insert")
    cursor.execute("""
        CREATE TRIGGER trg_learner_insert AFTER INSERT ON Learners
        FOR EACH ROW BEGIN
            INSERT INTO AuditLog (ActionText)
            VALUES (CONCAT('INSERT: New learner added. Name: ', NEW.LearnerName, ' (ID: ', NEW.LearnerID, ')'));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_learner_update")
    cursor.execute("""
        CREATE TRIGGER trg_learner_update AFTER UPDATE ON Learners
        FOR EACH ROW BEGIN
            INSERT INTO AuditLog (ActionText)
            VALUES (CONCAT('UPDATE: Learner ID ', OLD.LearnerID, ' changed info (Name: ', OLD.LearnerName, ' -> ', NEW.LearnerName, ')'));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_learner_delete")
    cursor.execute("""
        CREATE TRIGGER trg_learner_delete AFTER DELETE ON Learners
        FOR EACH ROW BEGIN
            INSERT INTO AuditLog (ActionText)
            VALUES (CONCAT('DELETE: Learner removed. Name: ', OLD.LearnerName, ' (ID: ', OLD.LearnerID, ')'));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_instructor_insert")
    cursor.execute("""
        CREATE TRIGGER trg_instructor_insert AFTER INSERT ON Instructors
        FOR EACH ROW BEGIN
            INSERT INTO AuditLog (ActionText)
            VALUES (CONCAT('INSERT: New instructor added: ', NEW.InstructorName, ' (ID: ', NEW.InstructorID, ', Expertise: ', NEW.Expertise, ')'));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_instructor_update")
    cursor.execute("""
        CREATE TRIGGER trg_instructor_update AFTER UPDATE ON Instructors
        FOR EACH ROW BEGIN
            INSERT INTO AuditLog (ActionText)
            VALUES (CONCAT('UPDATE: Instructor ', OLD.InstructorName, ' (ID: ', OLD.InstructorID, ') info changed.'));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_instructor_delete")
    cursor.execute("""
        CREATE TRIGGER trg_instructor_delete AFTER DELETE ON Instructors
        FOR EACH ROW BEGIN
            INSERT INTO AuditLog (ActionText)
            VALUES (CONCAT('DELETE: Instructor removed: ', OLD.InstructorName, ' (ID: ', OLD.InstructorID, ')'));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_course_insert")
    cursor.execute("""
        CREATE TRIGGER trg_course_insert AFTER INSERT ON Courses
        FOR EACH ROW BEGIN
            INSERT INTO AuditLog (ActionText)
            VALUES (CONCAT('INSERT: New course added. Name: ', NEW.CourseName, ' (ID: ', NEW.CourseID, ')'));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_course_update")
    cursor.execute("""
        CREATE TRIGGER trg_course_update AFTER UPDATE ON Courses
        FOR EACH ROW BEGIN
            INSERT INTO AuditLog (ActionText)
            VALUES (CONCAT('UPDATE: Course ID ', OLD.CourseID, ' changed info (Name: ', OLD.CourseName, ' -> ', NEW.CourseName, ')'));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_course_delete")
    cursor.execute("""
        CREATE TRIGGER trg_course_delete AFTER DELETE ON Courses
        FOR EACH ROW BEGIN
            INSERT INTO AuditLog (ActionText)
            VALUES (CONCAT('DELETE: Course removed. Name: ', OLD.CourseName, ' (ID: ', OLD.CourseID, ')'));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_lecture_insert")
    cursor.execute("""
        CREATE TRIGGER trg_lecture_insert AFTER INSERT ON Lectures
        FOR EACH ROW BEGIN
            INSERT INTO AuditLog (ActionText)
            VALUES (CONCAT('INSERT: New lecture added to Course ', NEW.CourseID, '. Title: ', NEW.Title, ' (ID: ', NEW.LectureID, ')'));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_lecture_update")
    cursor.execute("""
        CREATE TRIGGER trg_lecture_update AFTER UPDATE ON Lectures
        FOR EACH ROW BEGIN
            INSERT INTO AuditLog (ActionText)
            VALUES (CONCAT('UPDATE: Lecture ID ', OLD.LectureID, ' in Course ', OLD.CourseID, ' changed info (Title: ', OLD.Title, ' -> ', NEW.Title, ')'));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_lecture_delete")
    cursor.execute("""
        CREATE TRIGGER trg_lecture_delete AFTER DELETE ON Lectures
        FOR EACH ROW BEGIN
            INSERT INTO AuditLog (ActionText)
            VALUES (CONCAT('DELETE: Lecture removed. Title: ', OLD.Title, ' (ID: ', OLD.LectureID, ') from Course ', OLD.CourseID));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_after_account_insert")
    cursor.execute("""
        CREATE TRIGGER trg_after_account_insert 
        AFTER INSERT ON Account 
        FOR EACH ROW 
        BEGIN
            INSERT INTO AuditLog (ActionText) 
            VALUES (CONCAT('New account created: ', NEW.Email, ' with Role ', NEW.Role));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_after_account_update")
    cursor.execute("""
        CREATE TRIGGER trg_after_account_update 
        AFTER UPDATE ON Account 
        FOR EACH ROW 
        BEGIN
            INSERT INTO AuditLog (ActionText) 
            VALUES (CONCAT('Account updated: ', NEW.Email, ' (Role changed from ', OLD.Role, ' to ', NEW.Role, ')'));
        END
    """)
    cursor.execute("DROP TRIGGER IF EXISTS trg_after_account_delete")
    cursor.execute("""
        CREATE TRIGGER trg_after_account_delete 
        AFTER DELETE ON Account 
        FOR EACH ROW 
        BEGIN
            INSERT INTO AuditLog (ActionText) 
            VALUES (CONCAT('Account deleted: ', OLD.Email, ' with Role ', OLD.Role));
        END
    """)
    # 6. Create Indexes
    index_queries = [
        "CREATE INDEX idx_course_name ON Courses(CourseName)",
        "CREATE INDEX idx_enrollment_learner ON Enrollments(LearnerID)",
        "CREATE INDEX idx_enrollment_course ON Enrollments(CourseID)"
    ]
    for query in index_queries:
        try:
            cursor.execute(query)
        except mysql.connector.Error as err:
            if err.errno == 1061:
                pass
            else:
                print(err)
    conn.commit()
    cursor.close()
    conn.close()

# --- Data Functions ---

def fetch_all(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def execute_write(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())
        conn.commit()
        if query.strip().upper().startswith(('UPDATE', 'DELETE')):
            return cursor.rowcount
        return cursor.lastrowid
    except Exception as e:
        conn.rollback()
        print(f"Database write error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def execute_proc(proc_name, args):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.callproc(proc_name, args)
    conn.commit()
    cursor.close()
    conn.close()

def add_learner(name, email, phone):
    """Generates an 8-digit LearnerID (YYYYXXXX) and inserts the learner."""
    current_year = datetime.datetime.now().year
    base_id = current_year * 10000
    max_id_limit = base_id + 9999
    query = "SELECT MAX(LearnerID) as max_id FROM Learners WHERE LearnerID >= %s AND LearnerID <= %s"
    results = fetch_all(query, (base_id, max_id_limit))
    max_id = results[0]['max_id'] if results else None
    new_learner_id = base_id if max_id is None else max_id + 1
    if new_learner_id > max_id_limit:
        raise OverflowError("ID capacity exceeded for the current year (maximum 9999 learners).")
    insert_query = "INSERT INTO Learners (LearnerID, LearnerName, Email, PhoneNumber) VALUES (%s, %s, %s, %s)"
    execute_write(insert_query, (new_learner_id, name, email, phone))
    return new_learner_id

def add_instructor(name, expertise, email):
    """Generates a 6-digit InstructorID (YYYYXX) and inserts the instructor."""
    current_year = datetime.datetime.now().year
    base_id = current_year * 100
    max_id_limit = base_id + 99
    query = "SELECT MAX(InstructorID) as max_id FROM Instructors WHERE InstructorID >= %s AND InstructorID <= %s"
    results = fetch_all(query, (base_id, max_id_limit))
    max_id = results[0]['max_id'] if results else None
    new_instructor_id = base_id if max_id is None else max_id + 1
    if new_instructor_id > max_id_limit:
        raise OverflowError("ID capacity exceeded for the current year (maximum 99 instructors).")
    insert_query = "INSERT INTO Instructors (InstructorID, InstructorName, Expertise, Email) VALUES (%s, %s, %s, %s)"
    execute_write(insert_query, (new_instructor_id, name, expertise, email))
    
    return new_instructor_id

def add_course(course_name, description, instructor_id):
    query = "INSERT INTO Courses (CourseName, Description, InstructorID) VALUES (%s, %s, %s)"
    return execute_write(query, (course_name, description, instructor_id))

def add_lecture(course_id, title, content):
    query = "INSERT INTO Lectures (CourseID, Title, Content) VALUES (%s, %s, %s)"
    return execute_write(query, (course_id, title, content))

def add_enrollment(learner_id, course_id):
    query = "INSERT INTO Enrollments (LearnerID, CourseID) VALUES (%s, %s)"
    return execute_write(query, (learner_id, course_id))

def add_account(email, password, role):
    if role not in [0, 1]:
        print("Invalid role. Must be 0 (Learner) or 1 (Instructor).")
        return False
        
    if fetch_all("SELECT Email FROM Account WHERE Email = %s", (email,)):
        print(f"Account with email {email} already exists.")
        return False
        
    try:
        execute_write("INSERT INTO Account (Email, Password, Role) VALUES (%s, %s, %s)", 
                      (email, generate_password_hash(password), role))
        return True
    except Exception:
        return False

def verify_account(email, password):
    result = fetch_all("SELECT Password, Role FROM Account WHERE Email = %s", (email,))
    if result:
        if check_password_hash(result[0]['Password'], password):
            return result[0]['Role']
        print("Invalid password.")
    else:
        print("Account not found.")
    return None

def insert_manager(email, plain_password):
    hashed_password = generate_password_hash(plain_password)
    query = "INSERT INTO Account (Email, Password, Role) VALUES (%s, %s, 2)"
    execute_write(query, (email, hashed_password))
    print(f"Success: Manager '{email}' created!")

# UPDATE/DELETE FUNCTIONS
def update_learner(name, email, phone):
    query = """
        UPDATE Learners 
        SET LearnerName = %s, PhoneNumber = %s 
        WHERE Email = %s
    """
    return execute_write(query, (name, phone, email))

def update_instructor(instructor_id, name, expertise, email):
    query = """
        UPDATE Instructors 
        SET InstructorName = %s, Expertise = %s, Email = %s 
        WHERE InstructorID = %s
    """
    return execute_write(query, (name, expertise, email, instructor_id))

def update_course(course_id, course_name, description, instructor_id):
    query = """
        UPDATE Courses 
        SET CourseName = %s, Description = %s, InstructorID = %s 
        WHERE CourseID = %s
    """
    return execute_write(query, (course_name, description, instructor_id, course_id))

def update_lecture(course_id, lecture_id, title, content):
    query = """
        UPDATE Lectures 
        SET Title = %s, Content = %s 
        WHERE CourseID = %s AND LectureID = %s
    """
    return execute_write(query, (title, content, course_id, lecture_id))

def delete_learner(learner_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        get_email_query = "SELECT Email FROM Learners WHERE LearnerID = %s"
        cursor.execute(get_email_query, (learner_id,))
        result = cursor.fetchone()
        learner_email = result[0] if result else None
        delete_enrollments_query = "DELETE FROM Enrollments WHERE LearnerID = %s"
        cursor.execute(delete_enrollments_query, (learner_id,))
        delete_learner_query = "DELETE FROM Learners WHERE LearnerID = %s"
        cursor.execute(delete_learner_query, (learner_id,))
        affected_rows = cursor.rowcount
        if learner_email:
            delete_account_query = "DELETE FROM Account WHERE Email = %s"
            cursor.execute(delete_account_query, (learner_email,))
        conn.commit()
        return affected_rows
    except mysql.connector.Error as db_err:
        conn.rollback()
        print(f"Database error occurred: {db_err}")
        raise
    finally:
        cursor.close()
        conn.close()

def delete_instructor(instructor_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        get_email_query = "SELECT Email FROM Instructors WHERE InstructorID = %s"
        cursor.execute(get_email_query, (instructor_id,))
        result = cursor.fetchone()
        instructor_email = result[0] if result else None
        unassign_courses_query = "UPDATE Courses SET InstructorID = NULL WHERE InstructorID = %s"
        cursor.execute(unassign_courses_query, (instructor_id,))
        delete_instructor_query = "DELETE FROM Instructors WHERE InstructorID = %s"
        cursor.execute(delete_instructor_query, (instructor_id,))
        affected_rows = cursor.rowcount
        if instructor_email:
            delete_account_query = "DELETE FROM Account WHERE Email = %s"
            cursor.execute(delete_account_query, (instructor_email,))
        conn.commit()
        return affected_rows 
    except mysql.connector.Error as db_err:
        conn.rollback()
        print(f"Database error occurred: {db_err}")
        raise
    finally:
        cursor.close()
        conn.close()

def delete_course(course_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        delete_lectures_query = "DELETE FROM Lectures WHERE CourseID = %s"
        cursor.execute(delete_lectures_query, (course_id,))
        delete_enrollments_query = "DELETE FROM Enrollments WHERE CourseID = %s"
        cursor.execute(delete_enrollments_query, (course_id,))
        delete_course_query = "DELETE FROM Courses WHERE CourseID = %s"
        cursor.execute(delete_course_query, (course_id,))
        conn.commit()
        return cursor.rowcount      
    except mysql.connector.Error as db_err:
        conn.rollback()
        print(f"Database error occurred: {db_err}")
        raise
    except Exception as e:
        conn.rollback()
        print(f"An error occurred: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def delete_enrollment(enrollment_id):
    return execute_write("DELETE FROM Enrollments WHERE EnrollmentID = %s", (enrollment_id,))

def delete_lecture(course_id, lecture_id):
    return execute_write("DELETE FROM Lectures WHERE CourseID = %s AND LectureID = %s", (course_id, lecture_id))

def reset_account(email):
    if not check_account_exists(email):
        print(f"Account with email {email} does not exist.")
        return False
    default_password = "123456"
    hashed_password = generate_password_hash(default_password)
    update_query = "UPDATE Account SET Password = %s WHERE Email = %s"
    execute_write(update_query, (hashed_password, email))
    return True

def update_password(email, password):
    return execute_write("UPDATE Account SET Password = %s WHERE Email = %s", (generate_password_hash(password), email))

# GET DATA
def get_instructor_workload():
    query = "SELECT * FROM v_instructor_load"
    return fetch_all(query)

def get_system_statistics():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True) 
    cursor.callproc('sp_system_statistics')
    results = []
    for result in cursor.stored_results():
        results.append(result.fetchall())
    return {
        'total_courses': results[0][0]['total_courses'] if results[0] else 0,
        'total_learners': results[1][0]['total_learners'] if results[1] else 0,
        'workload': results[2],
        'enrollment_trend': results[3]
    }

def learner_count(course_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True) 
    try:
        cursor.callproc('sp_course_summary', (course_id,))
        for result in cursor.stored_results():
            rows = result.fetchall()
            if rows:
                return rows[0]['TotalLearners']
        return 0
    except Exception as db_err:
        print(f"Database error in learner_count: {db_err}")
        return 0
    finally:
        cursor.close()
        conn.close()

def get_learner_by_email(email):
    query = "SELECT LearnerID, LearnerName, PhoneNumber FROM Learners WHERE Email = %s"
    results = fetch_all(query, (email,))
    return results[0] if results else None

def get_all_courses_with_instructors():
    query = """
        SELECT c.CourseID, c.CourseName, c.Description, i.InstructorName, i.Expertise, i.Email
        FROM Courses c
        LEFT JOIN Instructors i ON c.InstructorID = i.InstructorID
    """
    return fetch_all(query)

def get_enrolled_course_ids(email):
    query = """
        SELECT CourseID 
        FROM Enrollments 
        WHERE LearnerID = (SELECT LearnerID FROM Learners WHERE Email = %s)
    """
    results = fetch_all(query, (email,))
    return [row['CourseID'] for row in results]

def get_lectures_by_course(course_id):
    query = "SELECT LectureID, Title, Content FROM Lectures WHERE CourseID = %s ORDER BY LectureID ASC"
    return fetch_all(query, (course_id,))

def get_course_by_id(course_id):
    query = "SELECT CourseID, CourseName, Description FROM Courses WHERE CourseID = %s"
    results = fetch_all(query, (course_id,))
    return results[0] if results else None

def get_instructor_courses(email):
    query = """
        SELECT CourseID, CourseName, Description 
        FROM Courses 
        WHERE InstructorID = (SELECT InstructorID FROM Instructors WHERE Email = %s)
    """
    return fetch_all(query, (email,))

def get_instructor_by_email(email):
    query = "SELECT InstructorID, InstructorName, Expertise FROM Instructors WHERE Email = %s"
    results = fetch_all(query, (email,))
    return results[0] if results else None

def check_account_exists(email):
    query = "SELECT Email FROM Account WHERE Email = %s"
    results = fetch_all(query, (email,))
    return len(results) > 0

def get_all_instructors_with_courses():
    """Fetches all instructors and groups their assigned courses into a list."""
    query = """
        SELECT i.InstructorID, i.InstructorName, i.Expertise, i.Email , c.CourseName
        FROM Instructors i
        LEFT JOIN Courses c ON i.InstructorID = c.InstructorID
        ORDER BY i.InstructorName
    """
    rows = fetch_all(query)
    
    instructors_dict = {}
    for row in rows:
        inst_id = row['InstructorID']
        if inst_id not in instructors_dict:
            instructors_dict[inst_id] = {
                'InstructorID': inst_id,
                'InstructorName': row['InstructorName'],
                'Expertise': row['Expertise'],
                'Email': row['Email'],
                'Courses': []
            }
        if row['CourseName']:
            instructors_dict[inst_id]['Courses'].append(row['CourseName'])
            
    return list(instructors_dict.values())

def get_all_learners_with_courses():
    query = """
        SELECT l.LearnerID, l.LearnerName, l.Email, l.PhoneNumber, c.CourseName
        FROM Learners l
        LEFT JOIN Enrollments e ON l.LearnerID = e.LearnerID
        LEFT JOIN Courses c ON e.CourseID = c.CourseID
        ORDER BY l.LearnerID
    """
    rows = fetch_all(query)
    learners_dict = {}
    for row in rows:
        learner_id = row['LearnerID']
        if learner_id not in learners_dict:
            learners_dict[learner_id] = {
                'LearnerID': learner_id,
                'LearnerName': row['LearnerName'],
                'Email': row['Email'],
                'PhoneNumber': row['PhoneNumber'],
                'Courses': []
            }
        if row['CourseName']:
            learners_dict[learner_id]['Courses'].append(row['CourseName'])
    return list(learners_dict.values())

def search_courses_by_name(search_term):
    query = """
        SELECT c.CourseID, c.CourseName, c.Description, i.InstructorName, i.Expertise, i.Email
        FROM Courses c
        LEFT JOIN Instructors i ON c.InstructorID = i.InstructorID
        WHERE c.CourseName LIKE %s
    """
    like_term = f"%{search_term}%"
    return fetch_all(query, (like_term,))

