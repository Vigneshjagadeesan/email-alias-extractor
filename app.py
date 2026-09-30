import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import urllib.parse
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Website Email & Contact Extractor",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom JavaScript to Disable Right Click & Inspect Element Shortcuts
components.html("""
    <script>
    // Disable Right Click
    document.addEventListener('contextmenu', function(e) {
        e.preventDefault();
    }, false);

    // Disable Keyboard Inspection Shortcuts
    document.addEventListener('keydown', function(e) {
        // F12 key
        if (e.keyCode == 123) {
            e.preventDefault();
            return false;
        }
        // Ctrl+Shift+I (Inspect)
        if (e.ctrlKey && e.shiftKey && e.keyCode == 73) {
            e.preventDefault();
            return false;
        }
        // Ctrl+Shift+J (Console)
        if (e.ctrlKey && e.shiftKey && e.keyCode == 74) {
            e.preventDefault();
            return false;
        }
        // Ctrl+U (View Source)
        if (e.ctrlKey && e.keyCode == 85) {
            e.preventDefault();
            return false;
        }
        // Ctrl+S (Save Page)
        if (e.ctrlKey && e.keyCode == 83) {
            e.preventDefault();
            return false;
        }
    }, false);
    </script>
""", height=0)

# Custom CSS for Mobile & Desktop Responsive Design
st.markdown("""
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 100%;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        font-weight: bold;
    }
    @media (max-width: 768px) {
        .stTextArea textarea {
            font-size: 14px;
        }
    }
    </style>
""", unsafe_allow_html=True)

st.title("Website Email & Contact Extractor")
st.markdown("Extract ALL public Email Addresses and Phone/Contact Numbers with mobile & desktop friendly one-click actions.")

domains_input = st.text_area("Enter Target Domains (One per line)", value="l-bank.de", height=120)

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_PATTERN = r'(?:\+\d{1,3}[\s\-\.]?)?\(?\d{2,5}\)?[\s\-\.]?\d{3,5}[\s\-\.]?\d{3,5}'

SUB_PATHS = [
    "", "/contact", "/contact-us", "/kontakt", "/impressum", 
    "/about", "/about-us", "/presse", "/privacy", "/help", "/terms"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_and_extract_data(args):
    domain, path = args
    target_url = f"https://{domain}{path}"
    found_emails = set()
    found_phones = set()
    
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=3)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            text_content = soup.get_text()
            
            # 1. Extract Emails
            matches = re.findall(EMAIL_PATTERN, text_content)
            for email in matches:
                clean_email = email.lower().strip()
                if not any(clean_email.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']):
                    found_emails.add(clean_email)
                
            for a_tag in soup.find_all('a', href=True):
                if 'mailto:' in a_tag['href']:
                    mail = a_tag['href'].replace('mailto:', '').split('?')[0].strip().lower()
                    if '@' in mail:
                        found_emails.add(mail)
                        
            # 2. Extract Phone Numbers
            for a_tag in soup.find_all('a', href=True):
                if 'tel:' in a_tag['href']:
                    phone = a_tag['href'].replace('tel:', '').strip()
                    if len(phone) >= 7:
                        found_phones.add(phone)
                        
            phone_matches = re.findall(PHONE_PATTERN, text_content)
            for phone in phone_matches:
                clean_phone = phone.strip()
                digits_only = re.sub(r'\D', '', clean_phone)
                if 7 <= len(digits_only) <= 15:
                    found_phones.add(clean_phone)
                    
    except Exception:
        pass
        
    return found_emails, found_phones

if st.button("Start Extraction", type="primary"):
    domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    
    all_emails = []
    all_phones = []
    
    status_text = st.empty()
    status_text.text("Scanning website pages at high speed...")
    
    for domain in domains:
        tasks = [(domain, path) for path in SUB_PATHS]
        
        domain_emails = set()
        domain_phones = set()
        
        with ThreadPoolExecutor(max_workers=15) as executor:
            results = executor.map(fetch_and_extract_data, tasks)
            for emails, phones in results:
                domain_emails.update(emails)
                domain_phones.update(phones)
                
        generic_prefixes = ['info', 'contact', 'kontakt', 'support', 'presse', 'service', 'help', 'sales', 'admin', 'office', 'post', 'mail']
        
        # Email Classification & Link Generation
        for email in domain_emails:
            prefix = email.split('@')[0]
            if email.endswith(f"@{domain}"):
                category = "Official Department Alias" if any(p in prefix for p in generic_prefixes) else "Official Direct Staff Email"
            else:
                category = "External / Other Email"
                
            gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={urllib.parse.quote(email)}"
            
            all_emails.append({
                "Target Domain": domain,
                "Email Address": email,
                "Compose in Gmail": gmail_link,
                "Type": category
            })
            
        # Phone Numbers & Link Generation
        for phone in domain_phones:
            clean_digits = re.sub(r'[^0-9+]', '', phone)
            tel_link = f"tel:{clean_digits}"
            all_phones.append({
                "Target Domain": domain,
                "Phone Number": phone,
                "Click to Call": tel_link
            })

    status_text.text("Extraction Complete!")
    
    st.session_state['emails_df'] = pd.DataFrame(all_emails).drop_duplicates(subset=['Email Address']) if all_emails else pd.DataFrame()
    st.session_state['phones_df'] = pd.DataFrame(all_phones).drop_duplicates(subset=['Phone Number']) if all_phones else pd.DataFrame()

# --- DISPLAY TABS SECTION ---
if 'emails_df' in st.session_state or 'phones_df' in st.session_state:
    
    tab1, tab2 = st.tabs(["Extracted Emails", "Contact / Phone Numbers"])
    
    # EMAIL TAB
    with tab1:
        if 'emails_df' in st.session_state and not st.session_state['emails_df'].empty:
            df_e = st.session_state['emails_df'].copy()
            st.success(f"Found {len(df_e)} total email addresses!")
            
            type_filter = st.selectbox("Filter Emails:", ["All Emails", "Official Department Alias", "Official Direct Staff Email", "External / Other Email"])
            filtered_df_e = df_e if type_filter == "All Emails" else df_e[df_e['Type'] == type_filter]
            
            st.dataframe(
                filtered_df_e,
                column_config={
                    "Compose in Gmail": st.column_config.LinkColumn(
                        "Open Gmail Compose",
                        help="Click to open web Gmail compose tab with this email ID.",
                        display_text="Compose"
                    )
                },
                use_container_width=True
            )
            
            # Download Button
            csv_emails = filtered_df_e[['Target Domain', 'Email Address', 'Type']].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Extracted Emails (CSV)",
                data=csv_emails,
                file_name="extracted_emails.csv",
                mime="text/csv"
            )
            
            st.markdown("---")
            st.subheader("Copy Plain Email List")
            email_list_str = "\n".join(filtered_df_e['Email Address'].tolist())
            st.code(email_list_str, language="text")
        else:
            st.warning("No email addresses were found.")
            
    # PHONE TAB
    with tab2:
        if 'phones_df' in st.session_state and not st.session_state['phones_df'].empty:
            df_p = st.session_state['phones_df'].copy()
            st.success(f"Found {len(df_p)} total phone/contact numbers!")
            
            st.dataframe(
                df_p,
                column_config={
                    "Click to Call": st.column_config.LinkColumn(
                        "Call Number",
                        help="Tap/click to trigger dialer on mobile or desktop phone app.",
                        display_text="Call"
                    )
                },
                use_container_width=True
            )
            
            # Download Button
            csv_phones = df_p[['Target Domain', 'Phone Number']].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Contact Numbers (CSV)",
                data=csv_phones,
                file_name="extracted_phone_numbers.csv",
                mime="text/csv"
            )
            
            st.markdown("---")
            st.subheader("Copy Plain Phone List")
            phone_list_str = "\n".join(df_p['Phone Number'].tolist())
            st.code(phone_list_str, language="text")
        else:
            st.warning("No phone/contact numbers were found on the website pages.")
