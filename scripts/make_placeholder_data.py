"""Regenerate D.R.O.N.A. PLACEHOLDER data (curriculum + Nepali jobs).

These are clearly-marked dummy stand-ins so the whole pipeline runs end-to-end
before the real Softwarica curriculum + collected job postings exist. They are
idempotent and safe to re-run; replace them with real data and re-run the
pipeline when ready.

`data/raw/` is gitignored, so the curriculum docs do not travel with a git clone
- run this script after cloning (e.g. on Colab/Kaggle) to recreate them. The job
JSONs are tracked in git, but this script can recreate them too.

Usage:
    python scripts/make_placeholder_data.py
    python scripts/make_placeholder_data.py --curriculum-only
    python scripts/make_placeholder_data.py --jobs-only
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).parent.parent))

app = typer.Typer(help=__doc__)

ROOT = Path(__file__).parent.parent
CURRICULUM_DIR = ROOT / "data" / "raw" / "curriculum"
MANUAL_DIR = ROOT / "data" / "manual_collection"

_DUMMY_HEADER = (
    "<!-- DUMMY / PLACEHOLDER curriculum file for D.R.O.N.A. development.\n"
    "     Replace with the real Softwarica module descriptor before production use. -->\n\n"
)

# (code, title, year, semester, credits, is_core, description, [outcomes], [skills], [prereqs])
_MODULES = [
    ("4001COMP", "Introduction to Programming", 1, 1, 20, True,
     "This module introduces first-year BSc (Hons) Computing students to the fundamentals of "
     "programming using Python: problem decomposition, algorithmic thinking, variables, data "
     "types, control flow, functions and basic data structures, with disciplined debugging, "
     "testing and version control from the outset.",
     ["Write, test and debug small Python programs that solve well-defined problems.",
      "Apply core programming constructs including loops, conditionals and functions.",
      "Decompose a problem into a sequence of algorithmic steps.",
      "Use lists, dictionaries and strings to represent and manipulate data.",
      "Demonstrate disciplined use of version control and code documentation."],
     ["Python", "Algorithm design", "Debugging", "Testing", "Git", "Problem solving"], []),
    ("4002COMP", "Computer Architecture and Networks", 1, 2, 20, True,
     "A foundational understanding of how computers and networks operate: digital logic, the "
     "von Neumann architecture, the CPU fetch-execute cycle, memory hierarchies, number "
     "representation, and the OSI / TCP-IP networking models, IP addressing, routing and "
     "common application protocols, with hands-on network configuration.",
     ["Explain the major components of a computer system and how they interact.",
      "Describe how data is represented and processed at the hardware level.",
      "Outline the layered models of computer networking and the role of key protocols.",
      "Configure and troubleshoot a simple local area network.",
      "Relate architectural and networking constraints to software performance."],
     ["Networking", "Linux", "Computer architecture", "Troubleshooting", "Security awareness"], []),
    ("4004COMP", "Mathematics for Computing", 1, 2, 20, True,
     "Develops the discrete mathematics and statistical foundations of computer science: set "
     "theory, logic and proof, functions and relations, graph theory, combinatorics, "
     "probability and descriptive statistics, applied throughout with programming exercises.",
     ["Apply set theory, logic and proof techniques to computing problems.",
      "Model relationships and networks using graphs and trees.",
      "Use combinatorics and probability to reason about algorithms and data.",
      "Compute and interpret basic descriptive statistics.",
      "Translate mathematical concepts into working code."],
     ["Statistics", "Algorithm design", "Problem solving", "Python"], []),
    ("4006COMP", "Web Design and Development", 1, 2, 20, True,
     "Introduces the design and construction of client-side web applications: semantic HTML, "
     "responsive CSS layout, client-side interactivity with JavaScript, user-centred design, "
     "accessibility and usability evaluation, culminating in a responsive multi-page website.",
     ["Build accessible, responsive web pages using HTML and CSS.",
      "Add client-side interactivity using JavaScript and the DOM.",
      "Apply user-centred design and usability principles to an interface.",
      "Evaluate a website against accessibility and usability heuristics.",
      "Use Git and a deployment workflow to publish a website."],
     ["HTML", "CSS", "JavaScript", "UX", "UI", "Git"], []),
    ("5001COMP", "Data Structures and Algorithms", 2, 1, 20, True,
     "A rigorous treatment of the data structures and algorithms at the core of efficient "
     "software: arrays, linked lists, stacks, queues, trees, hash tables and graphs, with "
     "searching, sorting, traversal and shortest-path algorithms, and Big-O complexity "
     "analysis, reinforced with object-oriented design in Java.",
     ["Implement and apply fundamental data structures in an object-oriented language.",
      "Analyse the time and space complexity of algorithms using asymptotic notation.",
      "Select appropriate data structures and algorithms for a given problem.",
      "Design and implement recursive and graph-based algorithms.",
      "Evaluate trade-offs between competing algorithmic solutions."],
     ["Java", "Data structures", "Algorithm design", "OOP", "Problem solving"], ["4001COMP"]),
    ("5002COMP", "Database Systems", 2, 1, 20, True,
     "The design, implementation and management of relational databases: ER modelling, "
     "normalisation, the relational model, SQL for definition and querying, transactions, "
     "indexing and query optimisation, plus an overview of NoSQL and vector databases used in "
     "modern data-driven and AI applications.",
     ["Produce normalised relational schemas from a requirements specification.",
      "Write SQL queries to define, populate and interrogate a database.",
      "Explain transaction management, concurrency and integrity constraints.",
      "Apply indexing and basic query optimisation techniques.",
      "Compare relational, NoSQL and vector database approaches."],
     ["SQL", "Database", "Data structures", "Python"], ["4001COMP"]),
    ("5004COMP", "Software Engineering", 2, 2, 20, True,
     "The principles and practice of professional, team-based software engineering: the "
     "software development life cycle, requirements engineering, agile/Scrum, version control "
     "workflows, UML modelling, design patterns, automated testing and continuous integration, "
     "delivered through a team software project.",
     ["Elicit, document and prioritise software requirements.",
      "Apply agile project management practices including Scrum and sprint planning.",
      "Model software designs using UML and apply common design patterns.",
      "Implement automated testing and continuous integration pipelines.",
      "Collaborate effectively in a development team using Git workflows."],
     ["Agile", "Testing", "Git", "OOP", "Debugging", "Docker"], ["4001COMP", "5001COMP"]),
    ("6001COMP", "Machine Learning and Artificial Intelligence", 3, 1, 20, True,
     "The theory and practice of machine learning and AI: supervised and unsupervised "
     "learning, regression, classification, clustering, neural networks and deep learning, "
     "the applied workflow from data preparation to evaluation, and the ethics of deploying AI, "
     "using Python with scikit-learn and PyTorch.",
     ["Explain the principles of supervised and unsupervised machine learning.",
      "Prepare data and engineer features for a machine learning task.",
      "Train, tune and evaluate machine learning and neural network models.",
      "Critically assess the ethical and societal implications of AI systems.",
      "Implement an end-to-end machine learning solution in Python."],
     ["Machine Learning", "Python", "Statistics", "Algorithm design", "Data structures"],
     ["4004COMP", "5001COMP"]),
    ("6002COMP", "Individual Project", 3, 2, 40, True,
     "The capstone of the programme: a substantial, self-directed research and development "
     "project under academic supervision, requiring problem identification, a literature "
     "review, design, implementation and critical evaluation, delivered as a professional "
     "dissertation and demonstration with attention to research ethics.",
     ["Plan and manage a substantial individual project to a professional standard.",
      "Conduct a critical review of literature relevant to a computing problem.",
      "Design, implement and evaluate a non-trivial software or research artefact.",
      "Communicate technical work in a written dissertation and an oral demonstration.",
      "Reflect critically on the process, outcomes and ethical dimensions of the work."],
     ["Problem solving", "Machine Learning", "Python", "Testing", "Git", "Agile"], ["5004COMP"]),
    ("6006COMP", "Cyber Security", 3, 1, 20, False,
     "The principles, threats and defences of modern cyber security: the CIA triad, attack "
     "vectors, cryptography, authentication and access control, secure software development, "
     "and network and web application security, balancing offensive understanding with "
     "defensive practice within an ethical and legal framework.",
     ["Analyse security threats and model risk for a given system.",
      "Apply cryptographic and authentication mechanisms appropriately.",
      "Identify and remediate common software and web vulnerabilities.",
      "Conduct authorised security testing within an ethical and legal framework.",
      "Design layered defences and an incident response plan."],
     ["Security", "Networking", "Linux", "Python", "Testing"], ["4002COMP", "5004COMP"]),
]


def _module_md(m) -> str:
    code, title, year, sem, credits, core, desc, outcomes, skills, prereqs = m
    lines = [_DUMMY_HEADER.rstrip("\n"), ""]
    lines += [f"Module Code: {code}", f"Module Title: {title}",
              f"Year {year}", f"Semester: {sem}", f"Level {year + 3}",
              f"Credits: {credits}", "", "Module Description:", desc, "", "Learning Outcomes:"]
    lines += [f"- {o}" for o in outcomes]
    lines += ["", "Prerequisites:"]
    lines += ([f"- {p}" for p in prereqs] if prereqs else ["None."])
    lines += ["", "Skills Developed:"]
    lines += [f"- {s}" for s in skills]
    core_txt = "core" if core else "optional elective"
    lines += ["", f"This module is a {core_txt} module of the programme."]
    return "\n".join(lines) + "\n"


def _write_curriculum() -> int:
    CURRICULUM_DIR.mkdir(parents=True, exist_ok=True)
    for m in _MODULES:
        code, title = m[0], m[1]
        slug = title.lower().replace(" ", "_").replace("/", "_")
        path = CURRICULUM_DIR / f"{code}_{slug}.md"
        path.write_text(_module_md(m), encoding="utf-8")
    typer.echo(f"  curriculum: {len(_MODULES)} module docs -> {CURRICULUM_DIR}")
    return len(_MODULES)


# ── Jobs ────────────────────────────────────────────────────────────────────
def _pid(source, slug):
    return source[:2] + "_2026_" + hashlib.md5((source + slug).encode()).hexdigest()[:6]


def _post(source, title, employer, location, req, pref, exp, smin, smax, desc, url, posted):
    return {
        "posting_id": _pid(source, title + employer), "source": source, "tier": "nepal",
        "title": title, "employer": employer, "location": location,
        "skills_required": req, "skills_preferred": pref, "experience_years_min": exp,
        "salary_min_npr": smin, "salary_max_npr": smax, "description": desc,
        "posted_date": posted + "T00:00:00", "source_url": url, "is_synthetic": False,
    }


def _jobs_data():
    mk = _post
    return {
        "merojob": [
            mk("merojob", "Junior Python Developer", "Leapfrog Technology", "Lalitpur",
              ["Python", "Django", "REST APIs", "PostgreSQL", "Git"], ["Docker", "AWS"], 0, 40000, 65000,
              "Build and maintain backend services using Python and Django; write clean, tested code and integrate REST APIs in an Agile team.",
              "https://merojob.com/jr-python-developer", "2026-05-18"),
            mk("merojob", "Frontend Developer (React)", "Yomari Incorporated", "Kathmandu",
              ["JavaScript", "React", "HTML", "CSS", "REST APIs"], ["TypeScript", "Tailwind"], 1, 50000, 90000,
              "Develop responsive, accessible React interfaces and maintain shared component libraries.",
              "https://merojob.com/frontend-react", "2026-05-20"),
            mk("merojob", "Machine Learning Engineer", "Fusemachines", "Kathmandu",
              ["Python", "Machine Learning", "PyTorch", "Statistics", "SQL"], ["Deep Learning", "NLP"], 2, 90000, 160000,
              "Design, train and deploy ML models; prepare datasets, engineer features and evaluate models.",
              "https://merojob.com/ml-engineer", "2026-05-22"),
            mk("merojob", "QA / Automation Engineer", "Deerwalk", "Kathmandu",
              ["Testing", "Selenium", "Python", "SQL"], ["CI/CD", "Agile"], 1, 45000, 80000,
              "Design and execute manual and automated test plans and ensure software quality across releases.",
              "https://merojob.com/qa-automation", "2026-05-12"),
            mk("merojob", "DevOps Engineer", "Logpoint Nepal", "Lalitpur",
              ["Linux", "Docker", "CI/CD", "Networking"], ["Kubernetes", "AWS"], 2, 80000, 150000,
              "Own build and deployment pipelines, containerise services and maintain cloud and on-prem infrastructure.",
              "https://merojob.com/devops-engineer", "2026-05-09"),
            mk("merojob", "Data Analyst", "CloudFactory", "Kathmandu",
              ["SQL", "Python", "Statistics", "Excel"], ["Power BI", "Machine Learning"], 1, 55000, 95000,
              "Write SQL queries, build dashboards, run statistical analysis and present findings to stakeholders.",
              "https://merojob.com/data-analyst", "2026-05-17"),
            mk("merojob", "Android Developer", "eSewa (F1Soft)", "Kathmandu",
              ["Java", "Kotlin", "REST APIs", "Git"], ["Jetpack Compose"], 1, 60000, 110000,
              "Develop native Android applications for a leading digital wallet; integrate APIs and optimise performance.",
              "https://merojob.com/android-developer", "2026-05-19"),
            mk("merojob", "Cyber Security Analyst", "Vairav Technology", "Kathmandu",
              ["Security", "Networking", "Linux", "Python"], ["SIEM", "Penetration testing"], 2, 75000, 140000,
              "Monitor, detect and respond to security threats; conduct vulnerability assessments and support incident response.",
              "https://merojob.com/security-analyst", "2026-05-21"),
            mk("merojob", "Full Stack Developer", "Young Innovations", "Lalitpur",
              ["JavaScript", "React", "Node.js", "SQL", "Git"], ["TypeScript", "Docker"], 2, 70000, 130000,
              "Build React frontends and Node/Express APIs with relational data models in a collaborative team.",
              "https://merojob.com/fullstack-developer", "2026-05-13"),
            mk("merojob", "Database Administrator", "Verisk Nepal", "Kathmandu",
              ["SQL", "Database", "PostgreSQL", "Linux"], ["Oracle"], 3, 80000, 140000,
              "Administer and tune relational databases, manage backups and security and support schema design.",
              "https://merojob.com/dba", "2026-05-08"),
            mk("merojob", "UI/UX Designer", "Cedar Gate Technologies", "Kathmandu",
              ["UI", "UX", "Figma", "HTML", "CSS"], ["Design systems"], 1, 50000, 95000,
              "Design intuitive, accessible interfaces; create wireframes and prototypes and run usability evaluations.",
              "https://merojob.com/ui-ux-designer", "2026-05-16"),
        ],
        "jobsnepal": [
            mk("jobsnepal", "Python/Django Developer", "Genese Solution", "Kathmandu",
              ["Python", "Django", "REST APIs", "PostgreSQL"], ["AWS", "Docker"], 1, 55000, 100000,
              "Develop cloud-based web applications using Python and Django; implement APIs and deploy to cloud infrastructure.",
              "https://jobsnepal.com/python-django-dev", "2026-05-11"),
            mk("jobsnepal", "Junior Data Scientist", "Docsumo", "Lalitpur",
              ["Python", "Machine Learning", "Statistics", "SQL"], ["NLP"], 0, 60000, 110000,
              "Support the data science team in building document-AI models; clean data, prototype models and evaluate accuracy.",
              "https://jobsnepal.com/jr-data-scientist", "2026-05-14"),
            mk("jobsnepal", "Software Engineer (Java)", "Cotiviti Nepal", "Kathmandu",
              ["Java", "Data structures", "SQL", "OOP"], ["Spring", "Agile"], 1, 65000, 120000,
              "Build enterprise healthcare-analytics software in Java applying solid OOP and data-structure fundamentals.",
              "https://jobsnepal.com/software-engineer-java", "2026-05-10"),
            mk("jobsnepal", "IT Support / Network Engineer", "WorldLink Communications", "Kathmandu",
              ["Networking", "Linux", "Troubleshooting"], ["CCNA"], 1, 40000, 75000,
              "Provide network and systems support; configure routers and switches and maintain infrastructure uptime.",
              "https://jobsnepal.com/network-engineer", "2026-05-06"),
            mk("jobsnepal", "Flutter Developer", "Sastodeal", "Lalitpur",
              ["Dart", "Flutter", "REST APIs", "Git"], ["Firebase"], 1, 55000, 100000,
              "Build cross-platform mobile apps with Flutter; integrate REST APIs and ship to the app stores.",
              "https://jobsnepal.com/flutter-developer", "2026-05-13"),
            mk("jobsnepal", "Business Intelligence Analyst", "Khalti Digital Wallet", "Lalitpur",
              ["SQL", "Statistics", "Python", "Excel"], ["Power BI"], 2, 65000, 115000,
              "Build BI dashboards and reports for a fintech product; model data and communicate insights.",
              "https://jobsnepal.com/bi-analyst", "2026-05-18"),
        ],
        "internsathi": [
            mk("internsathi", "Python Developer Intern", "Leapfrog Technology", "Lalitpur",
              ["Python", "Git", "SQL"], ["Django"], 0, 15000, 20000,
              "Three-month internship supporting backend teams; learn production Python and contribute to real features.",
              "https://internsathi.com/python-intern", "2026-05-20"),
            mk("internsathi", "Frontend Developer Intern", "Yomari Incorporated", "Kathmandu",
              ["HTML", "CSS", "JavaScript", "Git"], ["React"], 0, 12000, 18000,
              "Internship building UI components and learning modern frontend workflows including React.",
              "https://internsathi.com/frontend-intern", "2026-05-21"),
            mk("internsathi", "Machine Learning Intern", "Fusemachines", "Kathmandu",
              ["Python", "Machine Learning", "Statistics"], ["PyTorch"], 0, 15000, 25000,
              "Hands-on ML internship: data preparation, model prototyping and evaluation under mentorship.",
              "https://internsathi.com/ml-intern", "2026-05-22"),
            mk("internsathi", "Data Analyst Intern", "CloudFactory", "Kathmandu",
              ["SQL", "Python", "Excel"], ["Statistics"], 0, 12000, 20000,
              "Support analytics projects: clean datasets, build basic dashboards and assist with reporting.",
              "https://internsathi.com/data-analyst-intern", "2026-05-17"),
        ],
        "kumarijobs": [
            mk("kumarijobs", "Software Engineer", "Cedar Gate Technologies", "Kathmandu",
              ["Java", "Python", "SQL", "OOP", "Git"], ["Spring"], 2, 70000, 130000,
              "Design and build healthcare software applying strong engineering fundamentals across services, data and APIs.",
              "https://kumarijob.com/software-engineer", "2026-05-12"),
            mk("kumarijobs", "Data Engineer", "Docsumo", "Lalitpur",
              ["Python", "SQL", "Database"], ["Spark", "AWS"], 2, 80000, 150000,
              "Build and maintain data pipelines; model data and ensure reliable data flow for analytics and ML.",
              "https://kumarijob.com/data-engineer", "2026-05-18"),
            mk("kumarijobs", "Security Engineer", "Vairav Technology", "Kathmandu",
              ["Security", "Linux", "Networking", "Python"], ["SIEM"], 3, 90000, 160000,
              "Lead security engineering: threat modelling, hardening, monitoring and incident response.",
              "https://kumarijob.com/security-engineer", "2026-05-20"),
            mk("kumarijobs", "Backend Developer (Python)", "Gurzu", "Kathmandu",
              ["Python", "Django", "REST APIs", "PostgreSQL"], ["FastAPI", "Docker"], 2, 70000, 125000,
              "Build robust backend services in Python; design APIs, model data and ensure quality through testing.",
              "https://kumarijob.com/backend-python", "2026-05-15"),
            mk("kumarijobs", "AI/NLP Engineer", "Paaila Technology", "Lalitpur",
              ["Python", "Machine Learning", "NLP", "Statistics"], ["PyTorch", "Robotics"], 2, 90000, 170000,
              "Build conversational AI and NLP systems, including for robotics products; train and deploy models.",
              "https://kumarijob.com/ai-nlp-engineer", "2026-05-22"),
        ],
        "linkedin": [
            mk("linkedin", "Graduate Software Engineer", "Cotiviti Nepal", "Kathmandu",
              ["Java", "Data structures", "SQL", "OOP"], ["Spring", "Agile"], 0, 60000, 95000,
              "Graduate programme for new computing graduates with structured training in enterprise software engineering.",
              "https://linkedin.com/jobs/graduate-software-engineer", "2026-05-10"),
            mk("linkedin", "Associate Data Scientist", "Fusemachines", "Kathmandu",
              ["Python", "Machine Learning", "Statistics", "SQL"], ["Deep Learning", "MLOps"], 1, 80000, 140000,
              "Develop, evaluate and deploy ML models end to end for global clients.",
              "https://linkedin.com/jobs/associate-data-scientist", "2026-05-19"),
            mk("linkedin", "Robotics Software Engineer", "Paaila Technology", "Lalitpur",
              ["Python", "Robotics", "Linux", "ROS"], ["C++", "Computer Vision"], 2, 90000, 170000,
              "Develop software for service robots: motion, perception and human-robot interaction using ROS2 and Python.",
              "https://linkedin.com/jobs/robotics-software-engineer", "2026-05-21"),
            mk("linkedin", "Cloud / DevOps Engineer", "Genese Solution", "Kathmandu",
              ["Linux", "AWS", "Docker", "CI/CD"], ["Kubernetes"], 2, 90000, 160000,
              "Operate cloud infrastructure for enterprise clients; automate deployments and implement observability.",
              "https://linkedin.com/jobs/cloud-devops-engineer", "2026-05-17"),
        ],
    }


def _write_jobs() -> int:
    total = 0
    for source, posts in _jobs_data().items():
        d = MANUAL_DIR / source
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{source}_placeholder_postings.json").write_text(
            json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        total += len(posts)
    typer.echo(f"  jobs: {total} dummy Nepali postings -> {MANUAL_DIR}")
    return total


@app.command()
def main(
    curriculum_only: bool = typer.Option(False, "--curriculum-only"),
    jobs_only: bool = typer.Option(False, "--jobs-only"),
) -> None:
    typer.secho("Writing D.R.O.N.A. placeholder data (replace with real data later)", bold=True)
    if not jobs_only:
        _write_curriculum()
    if not curriculum_only:
        _write_jobs()
    typer.secho("Done. Next: python scripts/prepare_training_data.py", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
