# Publication Reports

A personal weekly literature monitoring service with adaptive ranking.

Every Monday it fetches new publications from a list of journals you care about, sends you a short notification email, and gives you a simple web page where you mark the articles you find interesting. Over time it learns from your choices and reorders future digests so the most relevant articles appear first — drawing on the same active learning logic used in systematic review tools like ASReview.

---

## What happens each week

1. Monday morning: you receive a short email saying how many new publications have appeared across your journals, with a link.
2. You open the link. You see all articles for that week, ordered by how likely the system thinks you are to find them interesting. You tick the ones you want to read.
3. You click **Save Selections**. A follow-up email arrives with your selected articles in a readable format, plus files you can import directly into Zotero.
4. Your choices are stored and used to rerank next week's list.

---

## What you need

- A cloud server on AWS (this guide walks you through it — no prior experience needed)
- An email account for sending notifications — either a personal Gmail address or a free Brevo account (see the Configuration section)
- About 30–45 minutes for the initial setup

You do not need programming experience. You will type some commands into a terminal, but each step below explains what you are doing and why.

---

## Setting up a cloud server on AWS

The service needs to run somewhere that is always on and reachable by email links, so a small cloud server is the most practical option. AWS offers a free-tier server that is more than sufficient.

### Create an account and launch a server

1. Go to [aws.amazon.com](https://aws.amazon.com) and create a free account.
2. Once logged in, go to **EC2** (you can search for it) and click **Launch Instance**.
3. Give it a name (e.g. *pub-reports*).
4. Under **Application and OS Images**, choose **Ubuntu Server 22.04 LTS**.
5. Under **Instance type**, choose **t3.micro** (free tier eligible, perfectly adequate for this).
6. Under **Key pair**, click **Create new key pair**, name it something like *my-server-key*, and download the `.pem` file. Save this file somewhere safe — it is how you log into your server.
7. Under **Network settings**, make sure **Allow SSH traffic** is ticked, and also tick **Allow HTTP traffic from the internet**.
8. Click **Launch Instance**.

After a minute or two, your server will be running. Find its **Public IPv4 address** on the EC2 dashboard — you will need this.

### Open port 5000

The service runs on port 5000. You need to tell AWS to allow traffic through that port, otherwise your browser will not be able to reach the web interface.

1. In the EC2 dashboard, click **Security Groups** in the left menu.
2. Click the security group attached to your instance (it will be named something like *launch-wizard-1*).
3. Click the **Inbound rules** tab, then **Edit inbound rules**.
4. Click **Add rule**. Set the type to **Custom TCP**, the port to **5000**, and the source to **Anywhere-IPv4**.
5. Click **Save rules**.

### Connect to your server

On a Mac or Linux machine, open Terminal. On Windows, open PowerShell.

Navigate to where you saved the key file, then connect:

```bash
chmod 400 my-server-key.pem
ssh -i my-server-key.pem ubuntu@YOUR-SERVER-IP
```

Replace `YOUR-SERVER-IP` with the address from the EC2 dashboard. Type `yes` if asked to confirm. You are now inside your cloud server.

---

## Installing the software

Run these commands one at a time. Each line downloads or installs something the service depends on.

```bash
sudo apt update
sudo apt install -y python3-pip git nano cron
sudo systemctl enable cron
sudo systemctl start cron
pip3 install -r requirements.txt --break-system-packages
```

> The `--break-system-packages` flag is needed on newer versions of Ubuntu. It is safe to use here — it simply allows installing Python packages globally on the server.

Download this project onto your server:

```bash
git clone https://github.com/YOUR-USERNAME/publication-reports.git
cd publication-reports
pip3 install -r requirements.txt --break-system-packages
```

---

## Configuration

All settings live in a single file called `.env`. Make sure you are inside the project folder first:

```bash
cd ~/publication-reports
```

Then copy the template and open it for editing:

```bash
cp .env.example .env
nano .env
```

This opens a simple text editor. Use the arrow keys to move around. When you are done, press `Ctrl+X`, then `Y`, then `Enter` to save and exit.

The file contains lines starting with `#` — those are comments explaining each setting and are ignored by the programme. You only need to fill in the values on the lines that do not start with `#`.

### Email settings

The service needs an email account to send from. There are two options depending on your situation.

---

**Option A — Gmail (personal @gmail.com account only)**

Gmail allows you to create a special **App Password** — a separate 16-character password just for this application, so you never expose your main account password. This works only with a personal Gmail address, not with a Google Workspace account provided by a university or employer.

Step 1 — enable 2-Step Verification if you haven't already. App Passwords do not appear anywhere in Google's settings until this is turned on.

- Go to [myaccount.google.com](https://myaccount.google.com)
- Click **Security** in the left menu
- Under the section **How you sign in to Google**, click **2-Step Verification** and follow the steps to turn it on

Step 2 — create the App Password.

- Go back to [myaccount.google.com/security](https://myaccount.google.com/security)
- In the search bar at the top of that page, type **App Passwords** — this is the most reliable way to find it as Google moves it around
- Click the **App Passwords** result
- You will see a text box asking for a name — type anything, e.g. *pub-reports*, and click **Create**
- Google shows you a 16-character password in a box. Copy it now — it will not be shown again.

In your `.env` file:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your.address@gmail.com
SMTP_PASS=the-16-character-app-password
EMAIL_TO=the-address-where-you-want-to-receive-emails
```

---

**Option B — Brevo (recommended if Gmail doesn't work)**

Brevo is a free email sending service that is simpler to set up than Gmail and has no restrictions on account type. The free tier allows 300 emails per day, which is far more than this service ever needs.

- Go to [brevo.com](https://www.brevo.com) and create a free account
- Once logged in, go to your account menu (top right) → **SMTP & API**
- You will see an SMTP server address, port, login, and password already generated for you — copy these

In your `.env` file:

```
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USER=your-brevo-login
SMTP_PASS=your-brevo-smtp-password
EMAIL_TO=the-address-where-you-want-to-receive-emails
```

---

`EMAIL_TO` is where the weekly digest and selection emails will land. It can be any email address you prefer.

### The web address

When you save your selections, the service needs to know its own web address so it can include the correct link in emails. Use your server's IP address:

```
BASE_URL=http://YOUR-SERVER-IP:5000
```

### Security keys

The service uses two secret keys. Think of them like passwords — they are randomly generated strings of characters that protect the service from unwanted access:

- `SECRET_KEY` — used internally to make sure the login session stored in your browser cannot be tampered with.
- `ACCESS_TOKEN` — included in the link sent to you each Monday. Only someone who receives that email can access the web interface.

To generate these, you will run a short Python command that produces a random string. You do not need to understand the command itself — just run it and copy the output.

In your server terminal, run this command:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

It will print a long string of random letters and numbers, for example:
```
a3f8c2e1d094b7e6f1a2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4
```

Copy that output and paste it as the value for `SECRET_KEY` in your `.env` file.

Run the same command a second time to get a different random string for `ACCESS_TOKEN`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy that new output and paste it as `ACCESS_TOKEN`.

The result in your `.env` should look like this (with your own random strings):

```
SECRET_KEY=a3f8c2e1d094b7e6f1a2c3d4...
ACCESS_TOKEN=9f1b3e7a2c4d6f8b0e2a4c6d...
```

These values never need to change unless you suspect your email account has been compromised.

---

## First run

Make sure you are inside the project folder:

```bash
cd ~/publication-reports
```

Then load your settings and start the job:

```bash
set -a && source .env && set +a
python3 scripts/weekly_job.py
```

The `set -a && source .env && set +a` line reads your `.env` file and makes all the settings available to the programme. You will need to run it every time you open a fresh terminal session on the server — it does not persist between sessions.

If everything works, you should receive an email within a few minutes.

---

## Starting the web interface

The web interface needs to run continuously in the background so you can access it when you click the link in your email. Make sure you are inside the project folder and your settings are loaded:

```bash
cd ~/publication-reports
set -a && source .env && set +a
nohup python3 scripts/app.py &
```

`nohup` means "do not stop when I close this terminal window". The `&` runs it in the background. You may see a message saying `nohup: ignoring input and appending output to 'nohup.out'` — this is normal. You can now close your terminal and the service will keep running.

To check it is running:

```bash
pgrep -f app.py
```

If it prints a number, the service is running. If it prints nothing, it is not.

To stop it:

```bash
pkill -f app.py
```

> **Note:** If your server restarts (for example after an AWS maintenance event), you will need to start the web interface again by reconnecting via SSH and running the three commands above. For a fully automated setup where it restarts itself, look into Linux `systemd` services — but that is optional.

---

## Scheduling the weekly job

You want the fetch-and-email step to run automatically every Monday morning without you doing anything. Linux has a built-in scheduler called **cron** for exactly this.

Open the scheduler:

```bash
crontab -e
```

If it asks which editor to use, choose `nano` (usually option 1).

Add this line at the bottom of the file:

```
0 8 * * 1 cd /home/ubuntu/publication-reports && set -a && source .env && set +a && python3 scripts/weekly_job.py >> /home/ubuntu/weekly_job.log 2>&1
```

Save and exit (`Ctrl+X`, `Y`, `Enter`).

This tells the server to run the weekly job every Monday at 08:00 server time (UTC by default). To adjust for your timezone, change the `8` to the UTC equivalent of your preferred local time. For example, for 08:00 Central European Time in winter (UTC+1), use `7`.

---

## Using the service each week

Each Monday you will receive an email with a link. Click it. Your browser opens a page showing that week's publications. Once the model has learned from a few weeks of selections, articles are shown with a percentage score reflecting how likely you are to find them interesting.

Check the articles you want to engage with and click **Save Selections**. A follow-up email arrives with:

- A formatted list of your selected articles (`.md` file — readable in any text editor)
- A Zotero RIS import file (`.ris`) — open Zotero, go to **File → Import**, select this file
- A plain list of DOIs (`.txt`) — for Zotero's **Tools → Add Items by Identifier**, which fetches the most complete metadata

---

## Adding or removing journals

The list of journals is in `info/journal-info-comb.csv`. Open it in a spreadsheet application. Each row is a journal. The key columns are:

| Column | What it means |
|---|---|
| `group` | The thematic category shown as a section heading |
| `name` | The journal's display name |
| `o-issn` | The journal's online ISSN, used to query CrossRef |
| `crossref` | Set to `T` to include in the weekly fetch, anything else to exclude |

To add a journal, add a new row with those four fields filled in. The ISSN can be found on the journal's website or in any library catalogue.

---

## How the ranking works

The first few weeks the service has no information about your preferences, so articles appear in no particular order. As you make selections, the system builds up a picture of what you find interesting based on the words in titles and abstracts.

Technically it uses a method called TF-IDF (which measures how distinctive certain words are across a body of text) combined with logistic regression (a simple and interpretable classifier) to predict the probability that you would select any given article. The model is initialised with a set of pre-labeled articles so it is not starting from scratch.

You do not need to do anything to trigger retraining — it happens automatically each time the weekly job runs.
