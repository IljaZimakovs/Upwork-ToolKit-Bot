import os
import dotenv
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta, timezone
import asyncio
import telegram
from telegram import Bot  # Make sure to import Bot correctly
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build

# # Load environment variables
dotenv.load_dotenv()

# # Use os.getenv to retrieve environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# UPWORK_USERNAME = os.getenv("UPWORK_USERNAME")
# UPWORK_PASSWORD = os.getenv("UPWORK_PASSWORD")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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
worksheet = spreadsheet.get_worksheet(2)

worksheet_name = "Sheet3"

# If the worksheet is not found, create a new one
if worksheet is None:
    worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="100", cols="20")

# Define the header names
header_names = ["Posted", "Project Title", "Price", "Location", "Posted Jobs", "Hire Rate", "Total Spent", "Member Since", "Proposals", "Interviewing", "Invites sent", "Unasnwered invites", "Skills", "Project URL"]
existing_headers = worksheet.row_values(1)
if not existing_headers:
    worksheet.insert_row(header_names, index=1)

async def send_mail(content):
    bot = telegram.Bot(TELEGRAM_TOKEN)
    async with bot:
        chat_id = (await bot.get_updates())
        await bot.send_message(text=content, chat_id=TELEGRAM_CHAT_ID)

async def main():
    total_projects = []
    while True:
        try:
            file_path = 'past.html'
            url_path = 'past.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                html_content = file.read()
            with open(url_path, 'r', encoding='utf-8') as file:
                project_url = file.read()
            if project_url not in total_projects:
                total_projects.append(project_url)
                
                soup = BeautifulSoup(html_content, 'html.parser')
                for script_element in soup.find_all('script'):
                    if 'clientActivity' in script_element.text:
                        data = script_element.text
                        json_initial_text = data.split('clientActivity:{')[1].split('},weeklyRetainerBudget')[0]
                        proposals = str(json_initial_text.split(',')[1].split(':')[1])
                        break
                    else:
                        proposals = 'c'
                activity_items = soup.find('ul', class_='client-activity-items list-unstyled').find_all('li')
                viewed_time = 'Not viewed'  
                hires = '0'
                
                jst_timezone = timezone(timedelta(hours=9))
                current_date_time_jst = datetime.now(jst_timezone)
                posted_time = current_date_time_jst.strftime("%m/%d %H:%M") 
                
                project_title = soup.find('h4').text.strip()
                
                if soup.find(attrs={'data-test': 'PostedOn'}):
                    project_posted = soup.find(attrs={'data-test': 'PostedOn'}).find('span').text.strip()
                else:
                    project_posted = 'Unknown'
                    
                if soup.find(attrs={'data-test': 'Description'}):
                    project_description = soup.find(attrs={'data-test': 'Description'}).find('p').text.strip()
                else:
                    project_description = 'Unknown'
                    
                if soup.find(attrs={'data-test': 'BudgetAmount'}):
                    if 'hourly' in soup.find(class_='description').text.strip().lower():
                        project_price = f"{soup.find_all(attrs={'data-test': 'BudgetAmount'})[0].text.strip()}-{soup.find_all(attrs={'data-test': 'BudgetAmount'})[1].text.strip()}"
                    elif 'fixed' in soup.find(class_='description').text.strip().lower():
                        project_price = soup.find_all(attrs={'data-test': 'BudgetAmount'})[0].text.strip()
                else:
                    project_price = 'Hourly'
                
                if soup.find(class_='skills-list mt-3'):
                    project_skills = ', '.join(a.text for a in soup.find(class_='skills-list mt-3').find_all(attrs={"data-test": "Skill"})).strip()
                else:
                    project_skills = "No skills"
                
                if soup.find(attrs={'data-qa': 'client-location'}):
                    client_location = soup.find(attrs={'data-qa': 'client-location'}).find('strong').text.strip()
                else:
                    client_location = 'Unknown'
                    
                if soup.find(attrs={'data-qa': 'client-spend'}):
                    project_spent = soup.find(attrs={'data-qa': 'client-spend'}).find('span').text.replace('total spent', '').strip()
                else:
                    project_spent = 'No Spent'
                    
                if soup.find(attrs={'data-qa': 'client-job-posting-stats'}):
                    posted_jobs = soup.find(attrs={'data-qa': 'client-job-posting-stats'}).find('strong').text.strip().split(' ')[0]
                    hire_rate = soup.find(attrs={'data-qa': 'client-job-posting-stats'}).find('div').text.strip().split(' ')[0]
                else:
                    posted_jobs = 'Unknown'
                    hire_rate = 'Unknown'  
                                                                            
                if soup.find(attrs={'data-qa': 'client-contract-date'}):
                    member_since = soup.find(attrs={'data-qa': 'client-contract-date'}).text.strip().replace('Member since ', '')
                else:
                    member_since = 'Unknown'
                                            
                for item in activity_items:
                    chars_to_check = {'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'}

                    if 'Proposals:' in item.text and any(c in proposals.lower() for c in chars_to_check):
                        proposals = str(item.find(class_='value').text.replace('\n', '').strip())
                    if 'Last viewed by client' in item.text:
                        viewed_time = str(item.find(class_='value').text.replace('\n', '').strip())
                    if 'Hires:' in item.text:
                        hires = str(item.find(class_='value').text.replace('\n', '').strip())
                    if 'Interviewing' in item.text:
                        interviews = str(item.find(class_='value').text.replace('\n', '').strip())
                    if 'Invites sent:' in item.text:
                        invites_sent = str(item.find(class_='value').text.replace('\n', '').strip())
                    if 'Unanswered invites:' in item.text:
                        unanswered_invites = str(item.find(class_='value').text.replace('\n', '').strip())
                mark = '*****************************************************************'
                if int(interviews) < 1 and int(hires) < 1:
                    mark = '==================================================='
                    line = '-----------------------------------------------------------------------------------------------------'
                    message = project_title + '\n' + line + '\n' + '𝑷𝒓𝒊𝒄𝒆: ' + project_price + '\n' + '𝑷𝒐𝒔𝒕𝒆𝒅: ' + project_posted + ' from ' + posted_time + '\n' + line + '\n' '𝑷𝒓𝒐𝒋𝒆𝒄𝒕 𝑼𝑹𝑳: \n' + project_url + '\n'+ line + '\n' + '𝑳𝒐𝒄𝒂𝒕𝒊𝒐𝒏: ' + client_location + '\n' + '𝑷𝒐𝒔𝒕𝒆𝒅 𝑱𝒐𝒃𝒔: ' + posted_jobs + '\n' + '𝑯𝒊𝒓𝒆 𝑹𝒂𝒕𝒆: ' + hire_rate + '\n' + '𝑻𝒐𝒕𝒂𝒍 𝑺𝒑𝒆𝒏𝒕: ' + project_spent + '\n' + '𝑴𝒆𝒎𝒃𝒆𝒓 𝑺𝒊𝒏𝒄𝒆:  ' + member_since + "\n" + line + '\n' + '𝑫𝒆𝒔𝒄𝒓𝒊𝒑𝒕𝒊𝒐𝒏: ' + '\n' + project_description + "\n" + line + '\n' + '𝑺𝒌𝒊𝒍𝒍𝒔: ' + '\n' + project_skills + '\n' + line + '\n' + '𝑷𝒓𝒐𝒑𝒐𝒔𝒂𝒍𝒔: ' + proposals  + '\n' + '𝑳𝒂𝒔𝒕 𝒗𝒊𝒆𝒘𝒆𝒅 𝒃𝒚 𝒄𝒍𝒊𝒆𝒏𝒕: ' + viewed_time  + '\n' + '𝑯𝒊𝒓𝒆𝒔: ' + hires  + '\n' + '𝑰𝒏𝒕𝒆𝒓𝒗𝒊𝒆𝒘𝒊𝒏𝒈: ' + interviews  + '\n' + '𝑰𝒏𝒗𝒊𝒕𝒆𝒔 𝒔𝒆𝒏𝒕: ' + invites_sent  + '\n' + '𝑼𝒏𝒂𝒏𝒔𝒘𝒆𝒓𝒆𝒅 𝒊𝒏𝒗𝒊𝒕𝒆𝒔: ' + unanswered_invites + '\n' + mark
                    record = [f'{project_posted} from {posted_time}', project_title, project_price, client_location, posted_jobs, hire_rate, project_spent, member_since, proposals, interviews, invites_sent, unanswered_invites, project_skills, project_url.replace('URL: ', '')]
                    worksheet.append_row(record)
                    await send_mail(message)
                    print(project_url)
                    if len(total_projects) > 100:
                        total_projects = total_projects[-100:]
                    print('\n')
            time.sleep(5)
        except Exception as e:
            print(f'error: {e}')
            
if __name__ == "__main__":
    asyncio.run(main())