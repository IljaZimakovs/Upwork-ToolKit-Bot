import os
import dotenv
import time
import asyncio
import gspread
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from telegram import Bot
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build

# Load environment variables
dotenv.load_dotenv()

# Load Google Sheets credentials from environment variable
google_credentials_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH')
if not google_credentials_path:
    raise ValueError("The Google Sheets credentials path is not set in the environment variables")

# Set the scope and credentials for Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(google_credentials_path, scope)
client = gspread.authorize(creds)

# Open the Google Spreadsheet by title
sheet_url = "https://docs.google.com/spreadsheets/d/1lqSgbqWif-iyyL6KEOunCI7TaCGgIVC7P3__btNmjIE/edit?usp=sharing"
spreadsheet = client.open_by_url(sheet_url)
worksheet = spreadsheet.get_worksheet(0)
worksheet2 = spreadsheet.get_worksheet(1)
# worksheet3 = spreadsheet.get_worksheet(2)

worksheet_name = "Sheet1"
worksheet_name2 = "Sheet2"
worksheet_name3 = "Sheet3"


# If the worksheet is not found, create a new one
if worksheet is None:
    worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="100", cols="20")
if worksheet2 is None:
    worksheet2 = spreadsheet.add_worksheet(title=worksheet_name, rows="100", cols="20")
# if worksheet3 is None:
#     worksheet3 = spreadsheet.add_worksheet(title=worksheet_name, rows="100", cols="20")
            
# Define the header names
header_names = ["Posted", "Project Title", "Price", "Payment Status", "Total Spent", "Location", "Skills", "Project URL"]
existing_headers = worksheet.row_values(1)
if not existing_headers:
    worksheet.insert_row(header_names, index=1)


# Retrieve environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")

# Initialize the Telegram Bot outside the function
bot = Bot(token=TELEGRAM_TOKEN)

async def send_mail(chat_id, content):
    print(chat_id)
    try:
        await bot.send_message(chat_id=chat_id, text=content)
    except Exception as e:
        print(f"Failed to send message: {e}")

async def monitor_upwork():
    total_projects = []
    while True:
        try:
            file_path = 'upwork.html'

            try:
                # Check if the file exists
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as file:
                        html_content = file.read()
                        print("File read successfully.")
                else:
                    print("The file does not exist.")
                    continue
            except Exception as e:
                print(f'Error: File permission Error')
                continue

            soup = BeautifulSoup(html_content, 'html.parser')
            div_elements = soup.find_all(attrs={"data-ev-label": "search_results_impression"})
            div_elements.reverse()  # Process from newest to oldest

            for div in div_elements:
                project_details = parse_project(div)
                message = format_message(project_details)
                project = project_details[3]
                if project not in total_projects:
                    check_statement = f'{project_details[2]}{project_details[8]}'.lower()
                    keywords = {'extract', 'scrap', 'data', 'bot', 'automat', 'rpa', 'python', 'make.com', 'zapier', 'api', 'automation', 'software', 'pdf', 'chatgpt'}

                    project_record = [project_details[1], project_details[2], project_details[6], project_details[9], project_details[4], project_details[5], project_details[8], project_details[3]]
                    empty_record = ['', '', '', '', '', '', '', '.']
                    project_price = project_record[2]
                    if project_price in ("Hourly", "Fixed"):
                        worksheet.insert_row(project_record, 2)
                    elif "Hourly:" in project_price:
                        if float(project_price.split("-")[1].strip().replace("$", "")) > 20:
                            worksheet.insert_row(project_record, 2)
                    elif float(project_price.strip().replace("$", "").replace(",", "")) > 500:
                        worksheet.insert_row(project_record, 2)
                    else:
                        worksheet2.insert_row(project_record, 2)
                    time.sleep(1)
                total_projects.append(project)

                
            if len(total_projects) > 100:
                total_projects = total_projects[-100:]

            await asyncio.sleep(1)  # Sleep for 5 seconds before the next check

        except Exception as e:
            print(f'Error: {e}')
            await asyncio.sleep(60)  # Continue after a pause on error

def parse_project(div):
    """Extracts project details from a BeautifulSoup tag."""
    jst_timezone = timezone(timedelta(hours=9))
    current_date_time_jst = datetime.now(jst_timezone)
    posted_time = current_date_time_jst.strftime("%m/%d %H:%M")

    project_title = div.find('a', class_='up-n-link').text.strip()
    project_url = "https://www.upwork.com" + div.find('a', class_='up-n-link').get('href')
    project_posted = div.find(attrs={"data-test": "JobTileHeader"}).find('small').find_all('span')[1].text.strip() if div.find(attrs={"data-test": "JobTileHeader"}) else 'None'
    project_verified = div.find(attrs={"data-test": "payment-verified"}).text.strip() if div.find(attrs={"data-test": "payment-verified"}) else 'None'
    project_spent = div.find(attrs={"data-test": "total-spent"}).text.strip() if div.find(attrs={"data-test": "total-spent"}) else 'No spent'
    project_location = div.find(attrs={"data-test": "location"}).text.strip() if div.find(attrs={"data-test": "location"}) else 'None'
    project_price = div.find(attrs={"data-test": "job-type-label"}).text.strip() if 'Hourly' in div.text else div.find(attrs={"data-test": "is-fixed-price"}).find_all('strong')[1].text.strip()
    project_description = div.find(attrs={"data-test": "UpCLineClamp JobDescription"}).text.strip()
    if len(project_description) > 3000:
        project_description = project_description[:3000]
    project_skills = ', '.join(span.text for span in div.find_all(attrs={"data-test": "token"})) if div.find(attrs={"data-test": "TokenClamp JobAttrs"}) else "No skills"

    return [project_posted, posted_time, project_title, project_url, project_spent, project_location, project_price, project_description, project_skills, project_verified]

def format_message(details):
    mark = '===================================================='
    line = '---------------------------------------------------------------------------------------------------------'
    """Formats the project details into a message string."""
    return f"{details[2]}\n\n𝑷𝒐𝒔𝒕𝒆𝒅: {details[1]}\n𝑷𝒓𝒊𝒄𝒆: {details[6]}\n𝑳𝒐𝒄𝒂𝒕𝒊𝒐𝒏: {details[5]}\n𝑻𝒐𝒕𝒂𝒍 𝑺𝒑𝒆𝒏𝒕: {details[4]}\n\n𝑷𝒓𝒐𝒋𝒆𝒄𝒕 𝑼𝑹𝑳:\n{details[3]}\n\n𝑺𝒌𝒊𝒍𝒍𝒔:\n{details[8]}"

if __name__ == '__main__':
    asyncio.run(monitor_upwork())
