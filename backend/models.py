from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Association tables for many-to-many relationships
job_skills = db.Table('job_skills',
    db.Column('job_id', db.Integer, db.ForeignKey('job.id'), primary_key=True),
    db.Column('skill_id', db.Integer, db.ForeignKey('skill.id'), primary_key=True)
)

candidate_skills = db.Table('candidate_skills',
    db.Column('candidate_id', db.Integer, db.ForeignKey('candidate.id'), primary_key=True),
    db.Column('skill_id', db.Integer, db.ForeignKey('skill.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    full_name = db.Column(db.String(120))
    role = db.Column(db.String(50), default='recruiter')  # recruiter, admin, etc.
    organization = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50))  # technical, soft, language, etc.

    def __repr__(self):
        return f'<Skill {self.name}>'

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    required_skills = db.Column(db.Text)  # store as JSON or comma-separated for simplicity
    experience_required = db.Column(db.String(100))
    education_required = db.Column(db.String(200))
    location = db.Column(db.String(200))
    employment_type = db.Column(db.String(50))  # full-time, part-time, contract, remote
    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    requirements = db.Column(db.Text)
    status = db.Column(db.String(20), default='open')  # open, closed, draft
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', backref='created_jobs')
    applications = db.relationship('Application', backref='job', lazy='dynamic')

    def __repr__(self):
        return f'<Job {self.title}>'

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    resume_text = db.Column(db.Text)
    parsed_data = db.Column(db.Text)  # JSON string of parsed resume data
    current_status = db.Column(db.String(20), default='new')  # new, screening, shortlisted, interview, selected, rejected
    source = db.Column(db.String(50))  # uploaded, pasted, linkedin, etc.
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    skills = db.relationship('Skill', secondary=candidate_skills, backref=db.backref('candidates', lazy='dynamic'))
    applications = db.relationship('Application', backref='candidate', lazy='dynamic')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self):
        return f'<Candidate {self.full_name}>'

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='applied')  # applied, reviewed, shortlisted, interviewed, offered, rejected
    match_score = db.Column(db.Float)  # 0-100
    resume_score = db.Column(db.Float)
    jd_similarity = db.Column(db.Float)
    skill_overlap = db.Column(db.Float)
    role_confidence = db.Column(db.Float)
    notes = db.Column(db.Text)

    # Unique constraint
    __table_args__ = (db.UniqueConstraint('candidate_id', 'job_id', name='_candidate_job_uc'),)

    def __repr__(self):
        return f'<Application {self.candidate_id}-{self.job_id}>'

class Interview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'))
    interview_type = db.Column(db.String(50))  # technical, behavioral, hr, situational
    scheduled_at = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer)
    interviewer = db.Column(db.String(120))
    questions = db.Column(db.Text)  # JSON or text
    feedback = db.Column(db.Text)
    rating = db.Column(db.Integer)  # 1-5
    status = db.Column(db.String(20), default='scheduled')  # scheduled, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    application = db.relationship('Application', backref=db.backref('interviews', lazy='dynamic'))

    def __repr__(self):
        return f'<Interview {self.id} for Application {self.application_id}>'

class AptitudeTest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'))
    test_type = db.Column(db.String(50))  # quantitative, logical, verbal, technical
    score = db.Column(db.Integer)  # percentage
    max_score = db.Column(db.Integer, default=100)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    time_taken_seconds = db.Column(db.Integer)
    answers = db.Column(db.Text)  # JSON
    feedback = db.Column(db.Text)
    strength_areas = db.Column(db.Text)
    weakness_areas = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    application = db.relationship('Application', backref=db.backref('aptitude_tests', lazy='dynamic'))

    def __repr__(self):
        return f'<AptitudeTest {self.id} for Application {self.application_id}>'

