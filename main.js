require('dotenv').config();
const { chromium } = require('playwright');
const fs = require('fs').promises;
const TelegramBot = require('node-telegram-bot-api');
const { TELEGRAM_TOKEN, UPWORK_USERNAME, UPWORK_PASSWORD, TELEGRAM_CHAT_ID } = process.env;

const bot = new TelegramBot(TELEGRAM_TOKEN);

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function loginToWebsite() {
    const browser = await chromium.launch({ headless: false, args: ['--no-sandbox'] });
    const page = await browser.newPage();
    try {
        await page.goto('https://www.upwork.com/ab/account-security/login', { waitUntil: 'networkidle' });

        await page.fill('#login_username', UPWORK_USERNAME);
        await page.click('#login_password_continue');
        await page.waitForSelector('#login_password', { visible: true });
        await page.fill('#login_password', UPWORK_PASSWORD);
        await page.waitForSelector('#login_control_continue', { visible: true, timeout: 5000 });

        await page.click('#login_control_continue');
        await page.click('#login_control_continue');
        await page.click('#login_control_continue');
        await page.waitForNavigation({ waitUntil: 'networkidle' });
        console.log('Login successful');
        return { browser, page };
    } catch (error) {
        console.error('Login failed:', error);
        await browser.close();
        throw error;
    }
}

async function scrapeProjects(page) {
    let attempt = 0;
    const maxAttempts = 5; // Set the maximum number of retries

    while (attempt < maxAttempts) {
        try {
            attempt++;
            await page.goto("https://www.upwork.com/nx/search/jobs?amount=500-&category2_uid=531770282580668420,531770282580668419,531770282580668418&location=Americas,Antarctica,Asia,Europe,Oceania&payment_verified=1&sort=recency&t=0,1", { waitUntil: 'networkidle', timeout: 60000 });
            const html = await page.content();
            // Write the HTML content to a file
            await fs.writeFile('upwork_page.html', html, 'utf8');
            console.log('The HTML file has been saved on attempt ' + attempt);
            return html;
        } catch (error) {
            console.error('Scraping failed on attempt ' + attempt + ':', error);
            if (attempt >= maxAttempts) {
                throw new Error("Max retries reached, scraping failed: " + error.message);
            }
            console.log('Retrying in 10 seconds...');
            await sleep(10000); // Wait for 10 seconds before retrying
        }
    }
}


async function main() {
    let browser;
    try {
        const { browser: brwsr, page } = await loginToWebsite();
        browser = brwsr;
        let count = 0;
        
        while (true) {
            const html = await scrapeProjects(page);
            count ++;
            // Process the HTML or send a notification
            console.log(`New Project Scraped: Check your HTML file for details: ` + count);
            await sleep(100000); // Wait for 60 seconds before the next scrape
        }
    } catch (error) {
        console.error('Error in main:', error);
        if (browser) {
            await browser.close();
        }
    }
}

main();
