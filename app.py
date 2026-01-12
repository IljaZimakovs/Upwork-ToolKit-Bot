import os
import dotenv
import time
import asyncio
import gspread
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from telegram import Bot
from oauth2client.service_account import ServiceAccountCredentials


# Load environment variables
dotenv.load_dotenv()

# Load Google Sheets credentials from environment variable
google_credentials_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH')
if not google_credentials_path:
    raise ValueError("The Google Sheets credentials path is not set in the environment variables")

# Google Sheets authorization
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(google_credentials_path, scope)
client = gspread.authorize(creds)

# Open Google Spreadsheet
sheet_url = "https://docs.google.com/spreadsheets/d/1lqSgbqWif-iyyL6KEOunCI7TaCGgIVC7P3__btNmjIE/edit?usp=sharing"
spreadsheet = client.open_by_url(sheet_url)
worksheet = spreadsheet.get_worksheet(0)

# Add headers if missing
# NOTE: Location moved between Project Title and Details
header_names = [
    "Posted",
    "Project Title",
    "Location",
    "Details",
    "Payment Status",
    "Total Spent",
    "Description",
    "Skills",
    "Project URL",
]

if not worksheet.row_values(1):
    worksheet.insert_row(header_names, index=1)

# Telegram Bot
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
bot = Bot(token=TELEGRAM_TOKEN)


async def send_mail(chat_id, content):
    try:
        await bot.send_message(chat_id=chat_id, text=content)
    except Exception as e:
        print(f"Failed to send message: {e}")


def clean_text(value: str) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def get_latest_upwork_file(directory=".") -> str | None:
    candidates = []
    for name in os.listdir(directory):
        if name.lower().startswith("upwork") and name.lower().endswith(".html"):
            full = os.path.join(directory, name)
            if os.path.isfile(full):
                candidates.append(full)

    if not candidates:
        return None

    return max(candidates, key=os.path.getmtime)


# ------------ CATEGORY HELPERS ------------

def categorize_job(title: str, description: str, skills: str) -> str:
    """
    Rule-based job categorization based on your 3 profiles:
      - UI/UX Design
      - Mobile Development
      - Full Stack (.NET / C# / React / AI / Angular)
    Uses title + description + skills ONLY.
    """
    text = f"{title} {description} {skills}".lower()

    categories = {
        "UI/UX Design": [
            # Core
            "ui", "ux", "ui/ux", "ux/ui", "product design", "interface design",
            "user interface", "user experience", "ux research", "user research",
            "design system", "component library", "style guide",
            # Tools
            "figma", "adobe xd", "sketch", "invision", "zeplin",
            # Types of work
            "wireframe", "wireframing", "prototype", "prototyping",
            "high-fidelity", "low-fidelity", "lo-fi", "hi-fi",
            "landing page design", "web app design", "dashboard design",
            "saas dashboard", "web dashboard", "admin dashboard",
            "mobile app design", "app redesign", "website redesign",
            "responsive design", "responsive ui", "ui redesign",
        ],
        "Mobile Development": [
            # Platforms
            "android", "ios", "iphone", "ipad", "play store", "app store",
            # Tech
            "swift", "objective-c", "kotlin", "java (android)", "jetpack compose",
            "react native", "flutter", "dart",
            # Phrases
            "mobile app", "mobile application", "mobile development",
            "cross-platform", "cross platform",
            "apk", "ipa",
            "push notification", "push notifications",
            "in-app purchase", "in app purchase",
            "firebase", "onesignal",
            "background service", "background task",
        ],
        "Full Stack (.NET/React/AI)": [
            # Backend .NET / C#
            "asp.net", "asp .net", "asp.net core", ".net core", "dotnet", "c#",
            "asp.net mvc", "mvc", "web api", "rest api", "webapi",
            "entity framework", "ef core", "linq",
            "clean architecture", "ddd", "onion architecture",
            # Frontend JS frameworks
            "react", "react.js", "react js", "next.js", "nextjs",
            "angular", "angularjs", "typescript", "javascript",
            "spa", "single page application",
            # General full stack
            "full stack", "full-stack", "frontend and backend",
            "end-to-end", "end to end",
            # Cloud / DevOps
            "azure", "aws", "gcp", "docker", "kubernetes", "ci/cd",
            "pipeline", "azure devops", "github actions",
            # Data
            "sql server", "mssql", "postgresql", "mysql", "database design",
            # AI
            "ai", "openai", "chatgpt", "gpt", "llm",
            "machine learning", "ml", "rag", "langchain",
        ],
    }

    best_cat = "Other"
    best_score = 0

    for cat, keywords in categories.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_cat = cat

    return best_cat


def category_symbols(category: str) -> str:
    """
    Map category to a single prefix symbol for Google Sheet title.
    (Only used at the START of the title.)
    """
    mapping = {
        "UI/UX Design": "🎨",
        "Mobile Development": "📱",
        "Full Stack (.NET/React/AI)": "🧠",
        "Other": "",
    }
    return mapping.get(category, "")


# ------------ MAIN LOOP ------------

async def monitor_upwork():
    total_projects = []

    while True:
        try:
            file_path = get_latest_upwork_file(".")
            if not file_path:
                print("No upwork*.html file found. Waiting...")
                await asyncio.sleep(5)
                continue

            print(f"Using HTML file: {file_path}")

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
            except Exception:
                print("File read error")
                await asyncio.sleep(5)
                continue

            soup = BeautifulSoup(html_content, "html.parser")
            div_elements = soup.find_all(attrs={"data-ev-label": "search_results_impression"})
            div_elements.reverse()

            for div in div_elements:
                project_details = parse_project(div)
                if not project_details:
                    continue

                project_url = project_details[3]

                if project_url not in total_projects:
                    base_title = project_details[2]
                    location_text = project_details[5]
                    details_text = project_details[6]
                    description_text = project_details[7]
                    skills_text = project_details[8]

                    # --- CATEGORY TAGGING FOR SHEET TITLE ---
                    category = categorize_job(base_title, description_text, skills_text)
                    cat_sym = category_symbols(category)

                    sheet_title = base_title
                    if cat_sym:
                        sheet_title = f"{cat_sym} {sheet_title}"

                    # NOTE: Location moved between Title and Details
                    row = [
                        project_details[1],  # Posted timestamp
                        sheet_title,         # Decorated title for Google Sheet
                        location_text,       # Location (moved here)
                        details_text,        # Details
                        project_details[9],  # Payment Status
                        project_details[4],  # Total spent
                        description_text,    # Description
                        skills_text,         # Skills
                        project_details[3],  # URL
                    ]

                    try:
                        worksheet.insert_row(row, 2)
                        await send_mail(TELEGRAM_CHAT_ID, format_message(project_details))
                    except Exception as e:
                        print(f"Insert error: {e}")

                    time.sleep(1)

                total_projects.append(project_url)

            if len(total_projects) > 200:
                total_projects = total_projects[-200:]

            try:
                os.remove(file_path)
                print(f"Deleted processed file: {file_path}")
            except Exception:
                pass

            await asyncio.sleep(1)

        except Exception as e:
            print("Error:", e)
            await asyncio.sleep(30)


# ------------ PARSING ------------

def parse_project(div):
    try:
        # Timestamp
        jst = timezone(timedelta(hours=10))
        posted_time = datetime.now(jst).strftime("%m/%d %H:%M")

        # ----- TITLE -----
        title_link = (
            div.find("a", attrs={"data-test": "job-tile-title-link UpLink"})
            or div.find("a", class_="air3-link")
        )

        if not title_link:
            return None

        project_title = clean_text(title_link.get_text(separator=" ", strip=True))

        href = title_link.get("href", "")
        project_url = href if href.startswith("http") else "https://www.upwork.com" + href

        # ----- POSTED AGO -----
        header = div.find(attrs={"data-test": "JobTileHeader"})
        if header and header.find("small"):
            small = header.find("small")
            spans = small.find_all("span")
            if len(spans) > 1:
                project_posted = clean_text(spans[1].text)
            else:
                project_posted = clean_text(small.text)
        else:
            project_posted = "None"

        # ----- PAYMENT VERIFIED -----
        payment_el = div.find(attrs={"data-test": "payment-verified"})
        if payment_el:
            badge = payment_el.find(attrs={"data-test": "UpCVerifiedBadge"})
            sr = badge.find("span", class_="sr-only") if badge else None
            raw = sr.text.strip() if sr else ""
            project_verified = f"Payment {raw.lower()}" if raw else "Payment status unknown"
        else:
            project_verified = "None"

        project_verified = clean_text(project_verified)

        # ----- SPENT -----
        spent_el = div.find(attrs={"data-test": "total-spent"})
        if spent_el:
            strong = spent_el.find("strong")
            span = spent_el.find("span")
            if strong and span:
                project_spent = clean_text(f"{strong.text} {span.text}")
            else:
                project_spent = clean_text(spent_el.text)
        else:
            project_spent = "No spent"

        # ----- LOCATION -----
        loc_el = div.find(attrs={"data-test": "location"})
        if loc_el:
            sr = loc_el.find("span", class_="sr-only")
            if sr:
                sr.extract()
            project_location = clean_text(loc_el.text)
        else:
            project_location = "None"

        # ----- DETAILS (job type + level + budget + duration) -----
        job_info_ul = div.find("ul", attrs={"data-test": "JobInfo"})

        job_type = ""
        experience = ""
        duration = ""
        budget = ""

        if job_info_ul:
            # JOB TYPE (Fixed / Hourly / Hourly range)
            type_el = job_info_ul.find("li", attrs={"data-test": "job-type-label"})
            if type_el:
                job_type = clean_text(type_el.text)

            # EXPERIENCE LEVEL
            exp_el = job_info_ul.find("li", attrs={"data-test": "experience-level"})
            if exp_el:
                experience = clean_text(exp_el.text)

            # DURATION
            dur_el = job_info_ul.find("li", attrs={"data-test": "duration-label"})
            if dur_el:
                duration = clean_text(dur_el.text)

            # BUDGET (fixed price)
            fixed_el = job_info_ul.find("li", attrs={"data-test": "is-fixed-price"})
            if fixed_el:
                budget = clean_text(fixed_el.text)

            # HOURLY RANGE
            hourly_el = job_info_ul.find("li", attrs={"data-test": "is-hourly"})
            if hourly_el and not budget:
                budget = clean_text(hourly_el.text)

        details_parts = [x for x in [job_type, experience, budget, duration] if x]
        project_details_info = " | ".join(details_parts)

        # ----- DESCRIPTION -----
        desc_el = div.find("div", attrs={"data-test": "UpCLineClamp JobDescription"})
        description = clean_text(desc_el.text) if desc_el else ""
        if len(description) > 3000:
            description = description[:3000]

        # ----- SKILLS -----
        skills_el = div.find(attrs={"data-test": "TokenClamp JobAttrs"})
        if skills_el:
            skills = [
                clean_text(span.text)
                for span in skills_el.find_all(attrs={"data-test": "token"})
            ]
            skills_text = ", ".join(skills)
        else:
            skills_text = "No skills"

        return [
            project_posted,        # 0
            posted_time,           # 1
            project_title,         # 2
            project_url,           # 3
            project_spent,         # 4
            project_location,      # 5
            project_details_info,  # 6  DETAILS COLUMN
            description,           # 7
            skills_text,           # 8
            project_verified       # 9
        ]

    except Exception as e:
        print("Parse error:", e)
        return None


# ------------ TELEGRAM MESSAGE FORMAT ------------

def format_message(d):
    """
    Formats the project details into a Telegram message string.
    - Highlights embedded / firmware / hardware jobs.
    - Places Description AFTER Total Spent.
    """

    title = d[2] or ""
    description = d[7] or ""   # description is d[7]
    skills = d[8] or ""

    haystack = f"{title} {description} {skills}".lower()

    embedded_keywords = [
        "firmware", "embedded", "hardware", "iot",
        "c++", "microcontroller",
        "rtos", "freertos",
        "arduino", "esp32", "esp8266", "stm32", "cortex",
        "electric",
        "circuit", "schematic",
        "prototype", "pcb", "altium", "easyeda",
        "gerber", "bom", "dfm",
        "wifi", "bluetooth",
        "robotics", "sensor",
    ]

    if any(k in haystack for k in embedded_keywords):
        title = f"🔥 {title} 🔥"

    return (
        f"{title}\n\n"
        f"Posted: {d[1]}\n"
        f"Details: {d[6]}\n"
        f"Location: {d[5]}\n"
        f"Total Spent: {d[4]}\n\n"
        f"Description:\n{description}\n\n"
        f"Project URL:\n{d[3]}\n\n"
        f"Skills:\n{skills}"
    )


if __name__ == '__main__':
    asyncio.run(monitor_upwork())
