import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash
import backend
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler
from db_backup import backup_database

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(func=backup_database, trigger="interval", hours=12)
scheduler.start()

@app.route('/')
def index():
    """Redirects the root URL to the login page."""
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = backend.verify_account(email, password)
        if role is not None:
            session['email'] = email
            session['role'] = role
            if role == 0:
                learner_data = backend.get_learner_by_email(email)
                if learner_data:
                    session['user_id'] = learner_data['LearnerID']
                    session['user_name'] = learner_data['LearnerName']
                    session['phone'] = learner_data['PhoneNumber']
                else:
                    session['user_name'] = "New Learner"
                    session['phone'] = ""
                return redirect(url_for('dashboard'))
            elif role == 1:
                instructor_data = backend.get_instructor_by_email(email)
                if instructor_data:
                    session['user_id'] = instructor_data['InstructorID']
                    session['user_name'] = instructor_data['InstructorName']
                else:
                    session['user_name'] = "Instructor"
                return redirect(url_for('instructor_dashboard'))
            elif role == 2:
                session['user_name'] = "System Manager"
                return redirect(url_for('manager_dashboard'))
                
        else:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new learner registration."""
    if request.method == 'POST':
        learner_name = request.form['learner_name']
        email = request.form['email']
        phone_number = request.form['phone_number']
        password = request.form['password']
        role = int(request.form['role'])
        account_created = backend.add_account(email, password, role)
        if account_created:
            try:
                backend.add_learner(learner_name, email, phone_number)
                
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                print(f"Error creating learner profile: {e}")
                flash('Account created, but failed to create learner profile.', 'error')
                return redirect(url_for('register'))
        else:
            flash('Email already exists or invalid data.', 'error')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# LEARNER
@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        flash('Please login to access this page.', 'error')
        return redirect(url_for('login'))
    email = session['email']
    all_courses = backend.get_all_courses_with_instructors()
    enrolled_course_ids = backend.get_enrolled_course_ids(email)
    my_courses = [c for c in all_courses if c['CourseID'] in enrolled_course_ids]
    return render_template('dashboard.html', courses=all_courses, enrolled_course_ids=enrolled_course_ids, my_courses=my_courses)

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    if 'email' not in session:
        return redirect(url_for('login'))
    course = backend.get_course_by_id(course_id)
    lectures = backend.get_lectures_by_course(course_id)
    if not course:
        flash("Course not found!", "error")
        return redirect(url_for('dashboard'))   
    return render_template('course_detail.html', course=course, lectures=lectures)

@app.route('/enroll', methods=['POST'])
def enroll():
    if 'email' not in session:
        flash('Please login to enroll in courses.', 'error')
        return redirect(url_for('login'))
    user_id = session['user_id']
    course_id = request.form.get('course_id')
    try:
        backend.add_enrollment(user_id, course_id)
        flash('Successfully enrolled in the course!', 'success')       
    except Exception as e:
        if '1062' in str(e):
            flash('You are already enrolled in this course.', 'error')
        else:
            flash('An error occurred during enrollment. Please try again.', 'error')
            print(f"Enrollment error: {e}")
    return redirect(url_for('dashboard'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'email' not in session:
        return redirect(url_for('login'))
    email = session['email']
    name = request.form.get('learner_name')
    phone = request.form.get('phone_number')
    new_password = request.form.get('new_password')

    try:
        backend.update_learner(name, email, phone)
        if new_password and new_password.strip():
            backend.update_password(email, new_password)

        session['user_name'] = name
        session['phone'] = phone
        
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating profile: {e}', 'error')

    return redirect(url_for('dashboard'))

# INSTRUCTOR
@app.route('/instructor_dashboard')
def instructor_dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))     
    email = session['email']
    instructor_data = backend.get_instructor_by_email(email)
    teaching_courses = backend.get_instructor_courses(email)
    session['user_name'] = instructor_data['InstructorName']
    session['expertise'] = instructor_data['Expertise']
    return render_template('instructor_dashboard.html', courses=teaching_courses)

@app.route('/instructor/course/<int:course_id>')
def instructor_course_detail(course_id):
    if 'email' not in session or session.get('role') != 1:
        return redirect(url_for('login'))
    course = backend.get_course_by_id(course_id)
    lectures = backend.get_lectures_by_course(course_id)
    student_count = backend.learner_count(course_id)
    return render_template('instructor_course_detail.html', course=course, lectures=lectures, student_count=student_count)

@app.route('/update_instructor_profile', methods=['POST'])
def update_instructor_profile():
    if 'email' not in session or session.get('role') != 1:
        return redirect(url_for('login'))
    instructor_id = session.get('user_id')
    email = session.get('email')
    new_name = request.form.get('name')
    new_expertise = request.form.get('expertise')
    new_password = request.form.get('new_password')
    try:
        backend.update_instructor(instructor_id, new_name, new_expertise, email)
        if new_password and new_password.strip():
            backend.update_password(email, new_password)
        session['user_name'] = new_name
        session['expertise'] = new_expertise
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        print(f"Update Profile Error: {e}")
        flash('An error occurred while updating your profile.', 'error')
    return redirect(url_for('instructor_dashboard'))

@app.route('/instructor/add_course', methods=['POST'])
def instructor_add_course():
    if 'email' not in session or session.get('role') != 1:
        return redirect(url_for('login'))
    course_name = request.form.get('course_name')
    description = request.form.get('description')
    instructor_id = session.get('user_id')
    backend.add_course(course_name, description, instructor_id)
    flash('Course created successfully!', 'success')
    return redirect(url_for('instructor_dashboard'))

@app.route('/instructor/add_lecture', methods=['POST'])
def instructor_add_lecture():
    course_id = request.form.get('course_id')
    title = request.form.get('title')
    content = request.form.get('content')
    backend.add_lecture(course_id, title, content)
    flash('Lecture added successfully!', 'success')
    return redirect(url_for('instructor_dashboard'))

@app.route('/instructor/delete_lecture', methods=['POST'])
def instructor_delete_lecture():
    if 'email' not in session or session.get('role') != 1:
        return redirect(url_for('login'))
    lecture_id = request.form.get('lecture_id')
    course_id = request.form.get('course_id')
    if lecture_id:
        try:
            backend.delete_lecture(course_id, lecture_id)
            flash('Lecture deleted successfully!', 'success')
        except Exception as e:
            print(f"Error deleting lecture: {e}")
            flash('Failed to delete lecture. Please try again.', 'error')
    return redirect(url_for('instructor_course_detail', course_id=course_id))

# MANAGER
@app.route('/manager_dashboard')
def manager_dashboard():
    if 'email' not in session or session.get('role') != 2:
        flash('Access denied. Managers only.', 'error')
        return redirect(url_for('login'))
    instructors_list = backend.get_all_instructors_with_courses()
    courses = backend.get_all_courses_with_instructors()
    learners_list = backend.get_all_learners_with_courses()
    system_stats = backend.get_system_statistics()
    return render_template('manager_dashboard.html',
                           instructors=instructors_list,
                           learners=learners_list,
                           stats=system_stats,
                           courses = courses)

@app.route('/manager/add_instructor', methods=['POST'])
def manager_add_instructor():
    if 'email' not in session or session.get('role') != 2:
        return redirect(url_for('login'))
    name = request.form.get('instructor_name')
    expertise = request.form.get('expertise')
    email = request.form.get('email')
    password = request.form.get('password')
    try:
        account_created = backend.add_account(email, password, 1)
        if account_created:
            new_id = backend.add_instructor(name, expertise, email)
            flash(f'Successfully added Instructor {name} with ID: {new_id}', 'success')
        else:
            flash('Failed to add instructor. Email already exists.', 'error')
    except Exception as e:
        flash(f'Error adding instructor: {str(e)}', 'error')
    return redirect(url_for('manager_dashboard'))

@app.route('/manager/edit_instructor', methods=['POST'])
def manager_edit_instructor():
    if 'email' not in session or session.get('role') != 2:
        return redirect(url_for('login'))
    instructor_id = request.form.get('instructor_id')
    name = request.form.get('instructor_name')
    expertise = request.form.get('expertise')
    email = request.form.get('email')
    reset_pwd = request.form.get('reset_password') 
    try:
        backend.update_instructor(instructor_id, name, expertise, email)
        msg = f'Successfully updated instructor: {name}.'
        if reset_pwd == 'on':
            if backend.reset_account(email):
                msg += ' Password reset to default (123456).'
        flash(msg, 'success')
    except Exception as e:
        flash(f'Error updating instructor: {str(e)}', 'error')
    return redirect(url_for('manager_dashboard'))

@app.route('/manager/delete_instructor', methods=['POST'])
def manager_delete_instructor():
    if 'email' not in session or session.get('role') != 2:
        return redirect(url_for('login'))     
    instructor_id = request.form.get('instructor_id')
    try:
        backend.delete_instructor(instructor_id)
        flash(f'Successfully deleted instructor ID: {instructor_id}', 'success')
    except Exception as e:
        flash(f'Error deleting instructor: {str(e)}', 'error')
    return redirect(url_for('manager_dashboard'))

@app.route('/manager/edit_learner', methods=['POST'])
def manager_edit_learner():
    if 'email' not in session or session.get('role') != 2:
        return redirect(url_for('login'))
    email = request.form.get('email')
    name = request.form.get('learner_name')
    phone = request.form.get('phone_number')
    reset_pwd = request.form.get('reset_password')
    try:
        backend.update_learner(name, email, phone)
        msg = f'Successfully updated learner: {name}.'
        if reset_pwd == 'on':
            if backend.reset_account(email):
                msg += ' Password reset to default (123456).'
        flash(msg, 'success')
    except Exception as e:
        flash(f'Error updating learner: {str(e)}', 'error')
    return redirect(url_for('manager_dashboard'))

@app.route('/manager/delete_learner', methods=['POST'])
def manager_delete_learner():
    if 'email' not in session or session.get('role') != 2:
        return redirect(url_for('login'))
    learner_id = request.form.get('learner_id')
    try:
        backend.delete_learner(learner_id)
        flash(f'Successfully deleted learner ID: {learner_id}', 'success')
    except Exception as e:
        flash(f'Error deleting learner: {str(e)}', 'error')
    return redirect(url_for('manager_dashboard'))

@app.route('/manager/add_course', methods=['POST'])
def manager_add_course():
    """Handles the form submission to create a new course."""
    if 'email' not in session or session.get('role') != 2:
        return redirect(url_for('login'))
    course_name = request.form.get('course_name')
    description = request.form.get('description')
    instructor_id = request.form.get('instructor_id')
    try:
        backend.add_course(course_name, description, instructor_id)
        flash(f'Successfully added new course: {course_name}', 'success')
    except Exception as e:
        flash(f'Error adding course: {str(e)}', 'error')
        
    return redirect(url_for('manager_dashboard'))

@app.route('/manager/edit_course', methods=['POST'])
def manager_edit_course():
    if 'email' not in session or session.get('role') != 2:
        return redirect(url_for('login'))     
    course_id = request.form.get('course_id')
    course_name = request.form.get('course_name')
    description = request.form.get('description')
    instructor_id = request.form.get('instructor_id')
    print(f"--- THỬ EDIT COURSE: ID={course_id}, Name={course_name}, InstID={instructor_id} ---")
    if course_id and course_id.isdigit():
        try:
            backend.update_course(int(course_id), course_name, description, instructor_id)
            flash("Course updated successfully!", "success")
        except Exception as e:
            print(f"Error updating course: {e}")
            flash("Failed to update course. Please try again.", "error")
    else:
        flash("Invalid course ID.", "error")
    return redirect(url_for('manager_dashboard'))

@app.route('/manager/delete_course', methods=['POST'])
def manager_delete_course():
    if 'email' not in session or session.get('role') != 2:
        return redirect(url_for('login'))
    course_id = request.form.get('course_id')
    if course_id and course_id.isdigit():
        try:
            backend.delete_course(int(course_id))
            flash("Course deleted successfully!", "success")
        except Exception as e:
            print(f"Error deleting course: {e}")
            flash("Failed to delete course. There might be existing enrollments or lectures.", "error")
    else:
        flash("Invalid course ID.", "error")
    return redirect(url_for('manager_dashboard'))

@app.route('/manager/statistics')
def manager_statistics():
    if 'email' not in session or session.get('role') != 2:
        return redirect(url_for('login'))
    system_stats = backend.get_system_statistics()
    return render_template('statistics.html', stats=system_stats)

if __name__ == '__main__':
    backend.initialize_database()
    MANAGER_EMAIL = "admin@neu.edu.vn"
    MANAGER_PASSWORD = "secure_password_123"
    if not backend.check_account_exists(MANAGER_EMAIL):
        backend.insert_manager(MANAGER_EMAIL, MANAGER_PASSWORD)
    app.run(debug=True)