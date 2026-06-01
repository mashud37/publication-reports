# Publication Reports

A personal weekly literature monitoring service with adaptive ranking.

Every Monday it fetches new publications from a list of journals you care about, sends you a short notification email, and gives you a simple web page where you mark the articles you find interesting. Over time it learns from your choices and reorders future digests so the most relevant articles appear first — drawing on the same active learning logic used in systematic review tools like ASReview.

---

## What happens each week

1. Monday morning: a scheduled job fetches the new publications and sends you a short email with a link.
2. You open the link. You see all articles for that week, ordered by how likely the system thinks you are to find them interesting. You tick the ones you want to read.
3. You click **Save Selections**. A follow-up email arrives with your selected articles in a readable format, plus files you can import directly into Zotero.
4. Your choices are stored and used to rerank next week's list.

---

## What you need

- A Google Cloud account (free to create; payment method required for verification, but expected costs are well under $1/month)
- A personal Gmail address (the service sends emails through it — Google Workspace accounts will not work)
- About 45 minutes for the initial setup

You do not need programming experience. You will type some commands into a terminal, but each step explains what you are doing.

---

## How the pieces fit together

The service is made up of three parts:

- **Cloud Run** — runs the website when you click your weekly email link.
- **Cloud Scheduler** — wakes up Cloud Run every Monday morning to fetch new publications and send you the email.
- **Cloud Storage** — keeps your database (selection history and articles) safe between runs.

---

## Step 1 — Create a Google Cloud account and project

1. Go to [cloud.google.com](https://cloud.google.com) and click **Get started for free** (or **Console** if you already have a Google account).
2. Sign in with a Google account and add a payment method when prompted.
3. In the Google Cloud Console, find the project selector at the top of the page. Click it, then click **New Project**.
4. Name the project `pub-reports` and click **Create**.
5. Make sure the project selector now shows `pub-reports`. Everything below assumes you are working in this project.

---

## Step 2 — Install the Google Cloud command-line tool

The command-line tool is called `gcloud`. It lets you control your cloud project from your own computer.

### On macOS

Open **Terminal** (`Cmd+Space`, type *Terminal*). Run:

```bash
curl https://sdk.cloud.google.com | bash
```

Press Enter to accept defaults. When it asks to update your shell profile, type `Y`.

Close Terminal and open it again.

### On Windows

Download the installer from [cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install) and run it. Accept all defaults.

### On Linux

Follow [cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install) for your distribution.

### Log in and select your project

```bash
gcloud auth login
```

Your browser will open. Sign in and click **Allow**.

```bash
gcloud config set project pub-reports
```

If `pub-reports` was taken, Google gave the project a different ID (e.g. `pub-reports-12345`). Find it at the top of the Cloud Console and use that ID instead.

---

## Step 3 — Turn on the cloud services we need

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com cloudscheduler.googleapis.com storage.googleapis.com
```

This may take a minute.

---

## Step 4 — Create a storage bucket for the database

The bucket name uses your GCP project ID as a prefix to keep it unique. Replace `YOUR_PROJECT` below with your project ID:

```bash
gcloud storage buckets create gs://YOUR_PROJECT-pubrep-data --location=europe-west1 --labels=app=pub-reports
```

Write down the exact name — you will need it in Step 7.

> **Region:** `europe-west1` is used throughout this guide. Change it consistently if you prefer a different region.

---

## Step 5 — Download this project to your computer

```bash
git clone https://github.com/YOUR-USERNAME/publication-reports.git
cd publication-reports
```

Replace `YOUR-USERNAME` with the actual GitHub location of this project.

If you don't have `git`, download the project as a ZIP file from its GitHub page (green **Code** button → **Download ZIP**), unzip it, and `cd` into the unzipped folder.

---

## Step 6 — Create your settings file

The service's settings live in a file called `env.yaml`.

Make a copy of the template:

**macOS or Linux:**
```bash
cp env.yaml.example env.yaml
```

**Windows:**
```
copy env.yaml.example env.yaml
```

Open `env.yaml` in a plain text editor (TextEdit on Mac, Notepad on Windows — not Word). The format is `KEY: "value"`.

### Email settings (Gmail App Password)

Gmail uses a special **App Password** — a separate 16-character password just for this application. This works only with a personal Gmail address, not with a Google Workspace account.

**1. Enable 2-Step Verification** (App Passwords are hidden until this is on):

- Go to [myaccount.google.com](https://myaccount.google.com)
- Click **Security**
- Under **How you sign in to Google**, click **2-Step Verification** and follow the steps

**2. Create the App Password:**

- Go back to [myaccount.google.com/security](https://myaccount.google.com/security)
- In the search bar at the top, type **App Passwords** — this is the most reliable way to find it
- Click the **App Passwords** result
- Type a name (e.g. *pub-reports*) and click **Create**
- Copy the 16-character password — it will not be shown again
- Paste it immediately into `env.yaml` without spaces (Google shows it as four groups of four letters, but enter it as one continuous string)

In `env.yaml`:

```yaml
SMTP_HOST: "smtp.gmail.com"
SMTP_PORT: "587"
SMTP_USER: "your.address@gmail.com"
SMTP_PASS: "the16characterpassword"
EMAIL_TO: "where-you-want-to-receive-emails@example.com"
```

### Security keys

The service uses three secret keys:

- `SECRET_KEY` — secures your browser session.
- `ACCESS_TOKEN` — included in the link sent to you each Monday. Only someone who receives the email can access the web interface.
- `WEEKLY_JOB_TOKEN` — used by the scheduler when triggering the weekly fetch.

Generate three random strings by running this command three times:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Paste the three results into `env.yaml`, keeping the double quotes:

```yaml
SECRET_KEY: "a3f8c2e1d094b7e6f1a2c3d4e5f6a7b8..."
ACCESS_TOKEN: "9f1b3e7a2c4d6f8b0e2a4c6d8e0f2a4..."
WEEKLY_JOB_TOKEN: "5c7e9a1b3d5f7e9a1c3e5f7a9c1e3f5..."
```

> **Windows note:** if `python3` is not recognised, try `python` instead.

### Things to leave alone for now

- `BASE_URL` — leave as the placeholder. You will fill it in after the first deployment.
- `DB_PATH` — leave as `/mnt/data/publications.db`. This points the service at the storage bucket from Step 4.

Save and close the file.

---

## Step 7 — Deploy the service to Cloud Run

The first deployment takes about 5 minutes; later ones are faster.

Make sure you are in the project folder (`cd publication-reports`).

Replace `YOUR_PROJECT-pubrep-data` with the exact bucket name from Step 4, then run:

```bash
gcloud run deploy pubrep \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 1 \
  --concurrency 1 \
  --timeout 600 \
  --add-volume name=data,type=cloud-storage,bucket=YOUR_PROJECT-pubrep-data \
  --add-volume-mount volume=data,mount-path=/mnt/data \
  --env-vars-file env.yaml \
  --labels app=pub-reports
```

> **Windows PowerShell:** replace each `\` with a backtick `` ` ``, or put the whole command on one line with no backslashes.
> **Shortcut:** `deploy.sh` in this directory automates Steps 4–8 in one shot — see the script header for usage.

Type `Y` to confirm any prompts.

When it finishes you will see:

```
Service URL: https://pubrep-abc123-ew.a.run.app
```

**Copy that URL.** Open `env.yaml` and paste it as the value of `BASE_URL` (keep the double quotes). Save.

Run the same deploy command again so the service knows its own address. This takes about 2 minutes.

---

## Step 8 — Schedule the weekly job

You need:

- Your service URL (from Step 7)
- The `WEEKLY_JOB_TOKEN` value from `env.yaml`

Replace the two `PASTE_...` placeholders below and run:

```bash
gcloud scheduler jobs create http pubrep-weekly-sched \
  --location=europe-west1 \
  --schedule="0 8 * * 1" \
  --uri="PASTE_YOUR_SERVICE_URL/internal/run-weekly?token=PASTE_YOUR_WEEKLY_JOB_TOKEN" \
  --http-method=POST \
  --time-zone="Europe/Berlin" \
  --attempt-deadline=600s
```

- `0 8 * * 1` means *every Monday at 08:00*. Change the first two numbers (`minute hour`) for a different time.
- Change `Europe/Berlin` to your time zone if needed: `America/New_York`, `America/Los_Angeles`, `Europe/London`, `Asia/Tokyo`, `Australia/Sydney`. Full list at [en.wikipedia.org/wiki/List_of_tz_database_time_zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

---

## Step 9 — Test it

Trigger the job manually:

```bash
gcloud scheduler jobs run pubrep-weekly-sched --location=europe-west1
```

Within a couple of minutes you should receive an email titled "Publications — Week of …". Click the link, tick a few articles, click **Save Selections**, and a follow-up email should arrive with your selections.

If something goes wrong, see **Troubleshooting** below.

---

## Using the service each week

Each Monday you receive an email with a link. Click it. The page shows that week's publications. Once the model has learned from a few weeks of selections, articles are shown with a percentage score reflecting predicted relevance.

Tick the articles you want and click **Save Selections**. A follow-up email arrives with:

- A formatted list (`.md`) — readable in any text editor
- A Zotero RIS import file (`.ris`) — open Zotero, **File → Import**
- A plain DOI list (`.txt`) — for Zotero's **Tools → Add Items by Identifier**

---

## Adding or removing journals

The journal list lives in `info/journal-info-comb.csv`. Open it in a spreadsheet application. Key columns:

| Column | Meaning |
|---|---|
| `group` | Thematic category shown as a section heading |
| `name` | Journal display name |
| `o-issn` | Online ISSN, used to query CrossRef |
| `crossref` | `T` to include in the weekly fetch, anything else to exclude |

To add a journal, add a row with those four fields. Find the ISSN on the journal's website or in any library catalogue.

After editing, redeploy with the Step 7 command.

---

## How the ranking works

The first few weeks the service has no information about your preferences, so articles appear in no particular order. As you make selections, it builds a picture of what you find interesting based on the words in titles and abstracts.

It uses TF-IDF (which measures how distinctive certain words are across a body of text) combined with logistic regression to predict the probability that you would select any given article. The model is initialised with a set of pre-labeled articles so it is not starting from scratch.

Retraining happens automatically each time the weekly job runs.

---

## What it costs

Expected monthly usage:

- **Cloud Run compute** — a few minutes per week. A few cents.
- **Cloud Storage** — a few megabytes. A fraction of a cent.
- **Cloud Scheduler** — one job. Around ten cents.
- **Cloud Build** — a few cents per redeploy.

Typical total: well under $1/month.

To set a hard safety limit, go to the [Billing section of the Cloud Console](https://console.cloud.google.com/billing), click **Budgets & alerts**, and create a budget with an alert at e.g. $5/month.

---

## Updating the service

After any code or settings change, run the deploy command from Step 7 again. Cloud Run replaces the running service in place — no downtime, no separate stop step.

---

## Troubleshooting

### I clicked the link in my email and got an error

Check the live logs:

```bash
gcloud run services logs tail pubrep --region europe-west1
```

Click the link again and watch what appears.

### The Monday email never arrived

Run the job manually and watch the logs:

```bash
gcloud scheduler jobs run pubrep-weekly-sched --location=europe-west1
gcloud run services logs tail pubrep --region europe-west1
```

The most common cause is incorrect SMTP credentials in `env.yaml`. Make sure `SMTP_PASS` is the 16-character App Password with no spaces, and that `SMTP_USER` is a personal `@gmail.com` address.

### I want to inspect the database

Download it:

```bash
gcloud storage cp gs://YOUR_PROJECT-pubrep-data/publications.db ./publications.db
```

Open with [DB Browser for SQLite](https://sqlitebrowser.org/) (free).

### I want to delete everything and start over

```bash
gcloud run services delete pubrep --region europe-west1
gcloud scheduler jobs delete pubrep-weekly-sched --location=europe-west1
gcloud storage rm -r gs://YOUR_PROJECT-pubrep-data
```

You can then redo the setup from Step 4.
