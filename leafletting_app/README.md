# 📮 SUTRUK Leafletting Tracker App

This is a web app built with [Streamlit](https://streamlit.io/) to help SUTR volunteers record and visualize which streets have been leafletted.

It’s designed to:
- ✅ Let volunteers submit newly leafletted streets using a simple form
- 🗺️ Show a live map of already leafletted postcode areas
- 📊 Update a central Google Sheet in real-time
- 🌐 Work fully online — no local setup required

---

## 🚀 How to Use (as a volunteer)

1. Open the app in your browser (mobile-friendly!)
2. Select the postcode and street from dropdowns
3. Optionally leave a comment
4. Click **Submit** to mark the area as leafletted
5. See the map update with your contribution!

---

## 🧠 For Maintainers (Abby or others)

### ✅ What’s in this folder

- `app.py` – The main Streamlit app code
- `requirements.txt` – List of Python packages Streamlit Cloud installs automatically
- `.streamlit/secrets.toml` – Stores your Google Sheets API credentials (see below)
- `data/postcode_polygons.geojson` – Map shapes for postcodes (used to display coverage)

---

### 🔐 Google Sheets Setup

To connect the app to your master spreadsheet:

1. Create a Google Cloud project & service account  
2. Enable **Google Sheets API**
3. Download the service account key as JSON
4. **Do not commit the JSON to GitHub**
5. In Streamlit Cloud:
   - Go to your deployed app → Settings → Secrets
   - Add one key:
   - GOOGLE_SHEETS_CREDENTIALS = """ <contents of your service account JSON here> """

6. Share your Google Sheet with the service account’s email (e.g., `streamlit-bot@yourproject.iam.gserviceaccount.com`) as **Editor**

---

### 🌐 Deployment Notes (Streamlit Cloud)

- The app lives in `leafletting_app/app.py`
- `requirements.txt` and `.streamlit/` folder must be in the same folder
- Streamlit Cloud automatically installs all dependencies and runs the app

---

### ✏️ To Edit or Update the App

You can:
- Edit files directly in GitHub
- Or use Colab to test code (e.g., working with your data)  
- Push changes to GitHub and Streamlit Cloud will auto-update

---

### 🔄 Coming Soon Ideas

- ✅ Add filters to view specific wards or streets
- 🔍 Fuzzy matching or search input for easier street selection
- 📤 Export activity logs to CSV
- 👥 Add contributor logins (optional)

---

Built with 💛 by Abi & ChatGPT 😄
