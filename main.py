from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import csv
import io
import os

app = FastAPI(title="ProctorPlus API - Jiya Patel 25012022018")

# ==========================================
# CORS Middleware (GitHub Pages માટે)
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # GitHub Pages અને લોકલ બંનેમાંથી રિક્વેસ્ટ એક્સેપ્ટ કરશે
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "proctorplus.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # M1 & M2: Students Tables
    cursor.execute('CREATE TABLE IF NOT EXISTS pending_students (enrollment TEXT PRIMARY KEY, name TEXT, branch TEXT, email TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS students (enrollment TEXT PRIMARY KEY, name TEXT, branch TEXT, email TEXT, status TEXT DEFAULT "Approved")')
    
    # M3: Leave Management Table
    cursor.execute('CREATE TABLE IF NOT EXISTS leave_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, enrollment TEXT, from_date TEXT, to_date TEXT, reason TEXT, status TEXT DEFAULT "Pending")')
    
    # M4: Student Issues / Tickets Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            enrollment TEXT, 
            category TEXT, 
            priority TEXT, 
            description TEXT, 
            status TEXT DEFAULT "Open",
            reply TEXT DEFAULT ""
        )
    ''')
    
    # M5: Meetings / Counselling Table
    cursor.execute('CREATE TABLE IF NOT EXISTS meetings (id INTEGER PRIMARY KEY AUTOINCREMENT, enrollment_no TEXT, meeting_date TEXT, topic TEXT, remarks TEXT, status TEXT DEFAULT "Completed")')
    
    # M6: Tasks / Follow-ups Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            assigned_to TEXT,
            due_date TEXT,
            status TEXT DEFAULT "Pending"
        )
    ''')
    
    # M7: Announcements & Communication Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            message TEXT,
            target_audience TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Safe column check for student_issues reply
    try:
        cursor.execute('ALTER TABLE student_issues ADD COLUMN reply TEXT DEFAULT ""')
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

init_db()

# Pydantic Models
class StudentCreate(BaseModel):
    enrollment: str
    name: str
    branch: str
    email: str

class LeaveRequestCreate(BaseModel):
    enrollment: str
    from_date: str
    to_date: str
    reason: str

class IssueCreate(BaseModel):
    enrollment: str
    category: str
    priority: str
    description: str

class IssueReplyUpdate(BaseModel):
    status: str
    reply: str

class MeetingCreate(BaseModel):
    enrollment_no: str
    meeting_date: str
    topic: str
    remarks: str

class TaskCreate(BaseModel):
    title: str
    description: str
    assigned_to: str
    due_date: str

class AnnouncementCreate(BaseModel):
    title: str
    message: str
    target_audience: str


# API Endpoints
@app.get("/")
def read_root():
    return {"message": "Welcome to ProctorPlus API! Jiya Patel - 25012022018"}


# ==========================================
# M1 & M2: Student Master & Attendance/Snapshot
# ==========================================
@app.post("/api/students/register")
def register_student(student: StudentCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO pending_students VALUES (?, ?, ?, ?)", (student.enrollment, student.name, student.branch, student.email))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail="Error registering student.")
    conn.close()
    return {"message": "Success"}

@app.get("/api/students/pending")
def get_pending_students():
    conn = get_db()
    rows = conn.execute("SELECT * FROM pending_students").fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/students/approved")
def get_approved_students():
    conn = get_db()
    rows = conn.execute("SELECT * FROM students").fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/students/approve/{enrollment}")
def approve_student(enrollment: str):
    conn = get_db()
    cursor = conn.cursor()
    student = cursor.execute("SELECT * FROM pending_students WHERE enrollment = ?", (enrollment,)).fetchone()
    if student:
        cursor.execute("INSERT OR REPLACE INTO students (enrollment, name, branch, email, status) VALUES (?, ?, ?, ?, 'Approved')", (student['enrollment'], student['name'], student['branch'], student['email']))
        cursor.execute("DELETE FROM pending_students WHERE enrollment = ?", (enrollment,))
        conn.commit()
        conn.close()
        return {"message": "Approved"}
    conn.close()
    raise HTTPException(status_code=404, detail="Not found")

@app.delete("/api/students/approved/{enrollment}")
def delete_approved_student(enrollment: str):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM students WHERE enrollment = ?", (enrollment,))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()
    return {"message": "Student removed successfully"}


# ==========================================
# M3: Leave Management
# ==========================================
@app.post("/api/leaves")
def create_leave(leave: LeaveRequestCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO leave_requests (enrollment, from_date, to_date, reason, status) VALUES (?, ?, ?, ?, ?)",
            (leave.enrollment, leave.from_date, leave.to_date, leave.reason, "Pending")
        )
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()
    return {"message": "Leave request submitted successfully"}

@app.get("/api/leaves")
def get_all_leaves():
    conn = get_db()
    rows = conn.execute("SELECT * FROM leave_requests").fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ==========================================
# M4: Student Issue / Ticket
# ==========================================
@app.post("/api/issues")
def create_issue(issue: IssueCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO student_issues (enrollment, category, priority, description, status, reply) VALUES (?, ?, ?, ?, ?, ?)",
            (issue.enrollment, issue.category, issue.priority, issue.description, "Open", "")
        )
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()
    return {"message": "Issue raised successfully"}

@app.get("/api/issues")
def get_all_issues():
    conn = get_db()
    rows = conn.execute("SELECT * FROM student_issues").fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.put("/api/issues/{issue_id}")
def update_issue(issue_id: int, data: IssueReplyUpdate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE student_issues SET status = ?, reply = ? WHERE id = ?",
            (data.status, data.reply, issue_id)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()
    return {"message": "Issue updated successfully"}

@app.delete("/api/issues/{issue_id}")
def delete_issue(issue_id: int):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM student_issues WHERE id = ?", (issue_id,))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()
    return {"message": "Issue deleted successfully"}


# ==========================================
# M5: Meetings / Counselling
# ==========================================
@app.post("/meetings/")
def create_meeting(meeting: MeetingCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO meetings (enrollment_no, meeting_date, topic, remarks, status) VALUES (?, ?, ?, ?, ?)",
            (meeting.enrollment_no, meeting.meeting_date, meeting.topic, meeting.remarks, "Completed")
        )
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()
    return {"message": "Meeting recorded successfully"}

@app.get("/meetings/")
def get_meetings():
    conn = get_db()
    rows = conn.execute("SELECT * FROM meetings").fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ==========================================
# M6: Tasks / Follow-ups
# ==========================================
@app.post("/api/tasks")
def create_task(task: TaskCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO tasks (title, description, assigned_to, due_date, status) VALUES (?, ?, ?, ?, 'Pending')",
            (task.title, task.description, task.assigned_to, task.due_date)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()
    return {"message": "Task created successfully"}

@app.get("/api/tasks")
def get_tasks():
    conn = get_db()
    rows = conn.execute("SELECT * FROM tasks").fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.put("/api/tasks/{task_id}/complete")
def complete_task(task_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = 'Completed' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return {"message": "Task marked as completed"}


# ==========================================
# M7: Announcement & Communication
# ==========================================
@app.post("/api/announcements")
def create_announcement(announcement: AnnouncementCreate):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO announcements (title, message, target_audience) VALUES (?, ?, ?)",
            (announcement.title, announcement.message, announcement.target_audience)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()
    return {"message": "Announcement broadcasted successfully"}

@app.get("/api/announcements")
def get_announcements():
    conn = get_db()
    rows = conn.execute("SELECT * FROM announcements ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ==========================================
# M8: Dashboard & Reports Summary
# ==========================================
@app.get("/api/reports/summary")
def get_reports_summary():
    conn = get_db()
    cursor = conn.cursor()
    
    total_students = cursor.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    pending_leaves = cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE status='Pending'").fetchone()[0]
    open_issues = cursor.execute("SELECT COUNT(*) FROM student_issues WHERE status='Open'").fetchone()[0]
    total_meetings = cursor.execute("SELECT COUNT(*) FROM meetings").fetchone()[0]
    
    conn.close()
    
    return {
        "total_students": total_students,
        "pending_leaves": pending_leaves,
        "open_issues": open_issues,
        "total_meetings": total_meetings
    }


# ==========================================
# M9: AI Assistant - Natural Language Query
# ==========================================
@app.post("/api/ai/query")
def ai_assistant_query(query: str = Form(...)):
    user_q = query.lower()
    conn = get_db()
    cursor = conn.cursor()
    response_text = ""
    
    try:
        if "રજા" in user_q or "leave" in user_q:
            cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE status='Pending'")
            count = cursor.fetchone()[0]
            response_text = f"સમીક્ષા મુજબ, હાલમાં કુલ {count} રજાઓની અરજીઓ મંજૂરી માટે પેન્ડિંગ છે."
            
        elif "પ્રશ્ન" in user_q or "issue" in user_q or "ticket" in user_q:
            cursor.execute("SELECT COUNT(*) FROM student_issues WHERE status='Open'")
            count = cursor.fetchone()[0]
            response_text = f"સિસ્ટમમાં હાલમાં કુલ {count} ઓપન સમસ્યાઓ (Issues) નિરાકરણ માટે બાકી છે."
            
        elif "विद्यार्थी" in user_q or "student" in user_q or "total" in user_q:
            cursor.execute("SELECT COUNT(*) FROM students")
            count = cursor.fetchone()[0]
            response_text = f"ડેટાબેઝમાં નોંધાયેલા કુલ સક્રિય વિદ્યાર્થીઓની સંખ્યા {count} છે."
            
        else:
            response_text = "માફ કરજો, હું આ પ્રશ્ન પૂરેપૂરો સમજી શક્યો નથી. તમે 'પેન્ડિંગ રજાઓ', 'ઓપન ઇશ્યૂ' અથવા 'કુલ વિદ્યાર્થીઓ' વિશે પૂછી શકો છો."
            
    except Exception as e:
        response_text = f"ડેટાબેઝ ક્વેરી રન કરતી વખતે એરર આવી છે: {str(e)}"
        
    conn.close()
    return {"query": query, "response": response_text}


# ==========================================
# M10: Administration - CSV Import
# ==========================================
@app.post("/api/admin/import-students")
async def import_students_csv(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    content = await file.read()
    stream = io.TextIOWrapper(io.BytesIO(content), encoding="utf-8")
    csv_reader = csv.reader(stream)
    
    next(csv_reader, None) # હેડર લાઇન છોડવા માટે
    
    conn = get_db()
    cursor = conn.cursor()
    count = 0
    
    try:
        for row in csv_reader:
            if len(row) >= 4:
                enrollment, name, branch, email = row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip()
                cursor.execute(
                    "INSERT OR REPLACE INTO students (enrollment, name, branch, email, status) VALUES (?, ?, ?, ?, 'Approved')",
                    (enrollment, name, branch, email)
                )
                count += 1
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Error processing CSV: {str(e)}")
    
    conn.close()
    return {"message": f"Successfully imported {count} students."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
