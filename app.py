import streamlit as st
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import pandas as pd
import urllib.parse
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Website Email & Contact Extractor",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Disable Right Click & Inspect Shortcuts
components.html("""
    <script>
    document.addEventListener('contextmenu', function(e) { e.preventDefault(); }, false);
    document.addEventListener('keydown', function(e) {
        if (e.keyCode == 123 || 
           (e.ctrlKey && e.shiftKey && (e.keyCode == 73 || e.keyCode == 74)) || 
           (e.ctrlKey && (e.keyCode == 85 || e.keyCode == 83))) {
            e.preventDefault();
            return false;
        }
    }, false);
    </script>
""", height=0)

st.markdown("""
    <style>
    .main .block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; max-width: 100%; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("Website Email & Contact Extractor")
st.markdown("Extract public Email Addresses and Phone/Contact Numbers at maximum speed.")

domains_input = st.text_area("Enter Target Domains (One per line)", value="l-bank.de", height=120)

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_PATTERN = r'(?:\+\d{1,3}[\s\-\.]?)?\(?\d{2,5}\)?[\s\-\.]?\d{3,5}[\s\-\.]?\d{3,5}'

SUB_PATHS = ["", "/contact", "/contact-us", "/kontakt", "/impressum", "/about", "/about-us", "/presse", "/privacy", "/help", "/terms"]
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

async def fetch_page(session, url):
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=1.5), ssl=False) as response:
            if response.status == 200:
                return await response.text()
    except Exception:
        pass
    return ""

async def process_domain(domain):
    found_emails, found_phones = set(), set()
    connector = aiohttp.TCPConnector(limit=50, ssl=False)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_page(session, f"https://{domain}{path}") for path in SUB_PATHS]
        pages_html = await asyncio.gather(*tasks)
        
        for html in pages_html:
            if not html:
                continue
            soup = BeautifulSoup(html, 'html.parser')
            text_content = soup.get_text()
            
            # Emails
            matches = re.findall(EMAIL_PATTERN, text_content)
            for email in matches:
                clean_email = email.lower().strip()
                if not any(clean_email.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']):
                    found_emails.add(clean_email)
                    
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if 'mailto:' in href:
                    mail = href.replace('mailto:', '').split('?')[0].strip().lower()
                    if '@' in mail:
                        found_emails.add(mail)
                elif 'tel:' in href:
                    phone = href.replace('tel:', '').strip()
                    if len(phone) >= 7:
                        found_phones.add(phone)
                        
            # Phones
            phone_matches = re.findall(PHONE_PATTERN, text_content)
            for phone in phone_matches:
                clean_phone = phone.strip()
                digits_only = re.sub(r'\D', '', clean_phone)
                if 7 <= len(digits_only) <= 15:
                    found_phones.add(clean_phone)
                    
    return found_emails, found_phones

if st.button("Start Extraction", type="primary"):
    domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    
    all_emails, all_phones = [], []
    status_text = st.empty()
    status_text.text("⚡ Ultra-Fast Async Scanning in progress...")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    for domain in domains:
        emails, phones = loop.run_until_complete(process_domain(domain))
        
        generic_prefixes = ['info', 'contact', 'kontakt', 'support', 'presse', 'service', 'help', 'sales', 'admin', 'office', 'post', 'mail']
        
        for email in emails:
            prefix = email.split('@')[0]
            category = "Official Department Alias" if (email.endswith(f"@{domain}") and any(p in prefix for p in generic_prefixes)) else ("Official Direct Staff Email" if email.endswith(f"@{domain}") else "External / Other Email")
            gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={urllib.parse.quote(email)}"
            all_emails.append({"Target Domain": domain, "Email Address": email, "Compose in Gmail": gmail_link, "Type": category})
            
        for phone in phones:
            clean_digits = re.sub(r'[^0-9+]', '', phone)
            all_phones.append({"Target Domain": domain, "Phone Number": phone, "Click to Call": f"tel:{clean_digits}"})

    status_text.text("Extraction Complete!")
    st.session_state['emails_df'] = pd.DataFrame(all_emails).drop_duplicates(subset=['Email Address']) if all_emails else pd.DataFrame()
    st.session_state['phones_df'] = pd.DataFrame(all_phones).drop_duplicates(subset=['Phone Number']) if all_phones else pd.DataFrame()

# --- DISPLAY SECTION ---
if 'emails_df' in st.session_state or 'phones_df' in st.session_state:
    tab1, tab2 = st.tabs(["Extracted Emails", "Contact / Phone Numbers"])
    
    with tab1:
        if 'emails_df' in st.session_state and not st.session_state['emails_df'].empty:
            df_e = st.session_state['emails_df'].copy()
            st.success(f"Found {len(df_e)} total email addresses!")
            type_filter = st.selectbox("Filter Emails:", ["All Emails", "Official Department Alias", "Official Direct Staff Email", "External / Other Email"])
            filtered_df_e = df_e if type_filter == "All Emails" else df_e[df_e['Type'] == type_filter]
            
            st.dataframe(filtered_df_e, column_config={"Compose in Gmail": st.column_config.LinkColumn("Open Gmail Compose", display_text="Compose")}, use_container_width=True)
            st.download_button("Download Extracted Emails (CSV)", filtered_df_e[['Target Domain', 'Email Address', 'Type']].to_csv(index=False).encode('utf-8'), "extracted_emails.csv", "text/csv")
            st.code("\n".join(filtered_df_e['Email Address'].tolist()), language="text")
        else:
            st.warning("No email addresses were found.")
            
    with tab2:
        if 'phones_df' in st.session_state and not st.session_state['phones_df'].empty:
            df_p = st.session_state['phones_df'].copy()
            st.success(f"Found {len(df_p)} total phone numbers!")
            st.dataframe(df_p, column_config={"Click to Call": st.column_config.LinkColumn("Call Number", display_text="Call")}, use_container_width=True)
            st.download_button("Download Contact Numbers (CSV)", df_p[['Target Domain', 'Phone Number']].to_csv(index=False).encode('utf-8'), "extracted_phone_numbers.csv", "text/csv")
            st.code("\n".join(df_p['Phone Number'].tolist()), language="text")
        else:
            st.warning("No phone/contact numbers were found.")
