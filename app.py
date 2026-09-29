import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Ultra-Fast Website Email Extractor", page_icon="⚡", layout="wide")

st.title("⚡ Ultra-Fast Website Email Extractor")
st.markdown("Extract ALL public email addresses (Official Domain & External Emails) found on target website pages at maximum speed.")

domains_input = st.text_area("Enter Target Domains (One per line)", value="l-bank.de", height=120)

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# High-priority sub-paths where emails are mostly found
SUB_PATHS = [
    "", "/contact", "/contact-us", "/kontakt", "/impressum", 
    "/about", "/about-us", "/presse", "/privacy", "/help", "/terms"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_and_extract_emails(args):
    domain, path = args
    target_url = f"https://{domain}{path}"
    found = set()
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=2.5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Plain text scan
            matches = re.findall(EMAIL_PATTERN, soup.get_text())
            for email in matches:
                clean_email = email.lower().strip()
                if not any(clean_email.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']):
                    found.add(clean_email)
                
            # mailto: links scan
            for a_tag in soup.find_all('a', href=True):
                if 'mailto:' in a_tag['href']:
                    mail = a_tag['href'].replace('mailto:', '').split('?')[0].strip().lower()
                    if '@' in mail:
                        found.add(mail)
    except Exception:
        pass
    return found

if st.button("Start Ultra-Fast Extraction", type="primary"):
    domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    all_results = []
    
    status_text = st.empty()
    status_text.text("Scanning website pages at max speed...")
    
    for domain in domains:
        tasks = [(domain, path) for path in SUB_PATHS]
        found_emails = set()
        
        with ThreadPoolExecutor(max_workers=15) as executor:
            results = executor.map(fetch_and_extract_emails, tasks)
            for email_set in results:
                found_emails.update(email_set)
                
        generic_prefixes = ['info', 'contact', 'kontakt', 'support', 'presse', 'service', 'help', 'sales', 'admin', 'office', 'post', 'mail']
        
        for email in found_emails:
            prefix = email.split('@')[0]
            
            if email.endswith(f"@{domain}"):
                category = "Official Department Alias" if any(p in prefix for p in generic_prefixes) else "Official Direct Staff Email"
            else:
                category = "External / Other Email"
                
            all_results.append({
                "Target Domain": domain,
                "Email Address": email,
                "Type": category
            })

    status_text.text("Extraction Complete!")
    
    if all_results:
        df = pd.DataFrame(all_results).drop_duplicates(subset=['Email Address'])
        st.session_state['extracted_df'] = df
    else:
        st.session_state['extracted_df'] = pd.DataFrame()
        st.warning("No public email addresses were found on the target website pages.")

# --- DISPLAY & COPY SECTION ---
if 'extracted_df' in st.session_state and not st.session_state['extracted_df'].empty:
    df = st.session_state['extracted_df']
    
    st.success(f"Found {len(df)} total email addresses!")
    
    type_filter = st.selectbox("Filter Results:", ["All Emails", "Official Department Alias", "Official Direct Staff Email", "External / Other Email"])
    filtered_df = df if type_filter == "All Emails" else df[df['Type'] == type_filter]
    
    st.dataframe(filtered_df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("📋 Copy Email List (Click top-right icon to Copy All)")
    
    email_list_str = "\n".join(filtered_df['Email Address'].tolist())
    st.code(email_list_str, language="text")
    
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Filtered Results as CSV",
        data=csv_data,
        file_name="website_emails.csv",
        mime="text/csv"
    )import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Ultra-Fast Website Email Extractor", page_icon="⚡", layout="wide")

st.title("⚡ Ultra-Fast Website Email Extractor")
st.markdown("Extract ALL public email addresses (Official Domain & External Emails) found on target website pages at maximum speed.")

domains_input = st.text_area("Enter Target Domains (One per line)", value="l-bank.de", height=120)

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# High-priority sub-paths where emails are mostly found
SUB_PATHS = [
    "", "/contact", "/contact-us", "/kontakt", "/impressum", 
    "/about", "/about-us", "/presse", "/privacy", "/help", "/terms"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_and_extract_emails(args):
    domain, path = args
    target_url = f"https://{domain}{path}"
    found = set()
    try:
        # Reduced timeout to 2.5s for max speed
        res = requests.get(target_url, headers=HEADERS, timeout=2.5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Plain text scan
            matches = re.findall(EMAIL_PATTERN, soup.get_text())
            for email in matches:
                clean_email = email.lower().strip()
                # Exclude image formats captured by wrong regex
                if not any(clean_email.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']):
                    found.add(clean_email)
                
            # mailto: links scan
            for a_tag in soup.find_all('a', href=True):
                if 'mailto:' in a_tag['href']:
                    mail = a_tag['href'].replace('mailto:', '').split('?')[0].strip().lower()
                    if '@' in mail:
                        found.add(mail)
    except Exception:
        pass
    return found

if st.button("Start Ultra-Fast Extraction", type="primary"):
    domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    all_results = []
    
    status_text = st.empty()
    status_text.text("Scanning website pages at max speed...")
    
    for domain in domains:
        tasks = [(domain, path) for path in SUB_PATHS]
        found_emails = set()
        
        # Max speed with 15 parallel threads
        with ThreadPoolExecutor(max_workers=15) as executor:
            results = executor.map(fetch_and_extract_emails, tasks)
            for email_set in results:
                found_emails.update(email_set)
                
        generic_prefixes = ['info', 'contact', 'kontakt', 'support', 'presse', 'service', 'help', 'sales', 'admin', 'office', 'post', 'mail']
        
        for email in found_emails:
            prefix = email.split('@')[0]
            
            # Classify into Official Domain Alias vs External Email
            if email.endswith(f"@{domain}"):
                category = "Official Department Alias" if any(p in prefix for p in generic_prefixes) else "Official Direct Staff Email"
            else:
                category = "External / Other Email"
                
            all_results.append({
                "Target Domain": domain,
                "Email Address": email,
                "Type": category
            })

    status_text.text("Extraction Complete!")
    
    if all_results:
        df = pd.DataFrame(all_results).drop_duplicates(subset=['Email Address'])
        st.session_state['extracted_df'] = df
    else:
        st.session_state['extracted_df'] = pd.DataFrame()
        st.warning("No public email addresses were found on the target website pages.")

# --- DISPLAY & COPY SECTION ---
if 'extracted_df' in st.session_state and not st.session_state['extracted_df'].empty:
    df = st.session_state['extracted_df']
    
    st.success(f"Found {len(df)} total email addresses!")
    
    # Filter dropdown
    type_filter = st.selectbox("Filter Results:", ["All Emails", "Official Department Alias", "Official Direct Staff Email", "External / Other Email"])
    filtered_df = df if type_filter == "All Emails" else df[df['Type'] == type_filter]
    
    st.dataframe(filtered_df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("📋 Copy Email List (Click top-right icon to Copy All)")
    
    email_list_str = "\n".join(filtered_df['Email Address'].tolist())
    st.code(email_list_str, language="text")
    
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Filtered Results as CSV",
        data=csv_data,
        file_name="website_emails.csv",
        mime="text/csv"
    )import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Fast Domain Email Alias Extractor", page_icon="⚡", layout="wide")

st.title("⚡ Fast Domain Email Alias Extractor")
st.markdown("Extract precise official department email aliases directly from target domain pages with high-speed scraping.")

domains_input = st.text_area("Enter Target Domains (One per line)", value="l-bank.de", height=120)

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# Key sub-paths where contact details & department aliases live
SUB_PATHS = [
    "", "/contact", "/contact-us", "/kontakt", "/impressum", 
    "/about", "/about-us", "/presse", "/privacy", "/help", "/terms"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_and_extract_emails(args):
    domain, path = args
    target_url = f"https://{domain}{path}"
    found = set()
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=4)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Plain text scan
            matches = re.findall(EMAIL_PATTERN, soup.get_text())
            for email in matches:
                found.add(email.lower().strip())
                
            # mailto: links scan
            for a_tag in soup.find_all('a', href=True):
                if 'mailto:' in a_tag['href']:
                    mail = a_tag['href'].replace('mailto:', '').split('?')[0].strip().lower()
                    if '@' in mail:
                        found.add(mail)
    except Exception:
        pass
    return found

if st.button("Start High-Speed Extraction", type="primary"):
    domains = [d.strip().replace("http://", "").replace("https://", "").strip("/") for d in domains_input.split("\n") if d.strip()]
    all_results = []
    
    status_text = st.empty()
    status_text.text("Fast multi-page scanning in progress...")
    
    for domain in domains:
        tasks = [(domain, path) for path in SUB_PATHS]
        found_emails = set()
        
        # Parallel scraping with 10 workers for max speed
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(fetch_and_extract_emails, tasks)
            for email_set in results:
                found_emails.update(email_set)
                
        # Filter strictly for target domain emails only
        generic_prefixes = ['info', 'contact', 'kontakt', 'support', 'presse', 'service', 'help', 'sales', 'admin', 'office', 'post', 'mail']
        
        for email in found_emails:
            if email.endswith(f"@{domain}"):
                prefix = email.split('@')[0]
                category = "Department Alias" if any(p in prefix for p in generic_prefixes) else "Direct Staff Email"
                
                all_results.append({
                    "Domain": domain,
                    "Email Address": email,
                    "Category": category
                })

    status_text.text("Extraction Complete!")
    
    if all_results:
        df = pd.DataFrame(all_results).drop_duplicates(subset=['Email Address'])
        st.session_state['extracted_df'] = df
    else:
        st.session_state['extracted_df'] = pd.DataFrame()
        st.warning("No official domain email aliases were found on the target website pages.")

# --- DISPLAY & COPY SECTION ---
if 'extracted_df' in st.session_state and not st.session_state['extracted_df'].empty:
    df = st.session_state['extracted_df']
    
    st.success(f"Found {len(df)} verified domain email addresses!")
    
    category_filter = st.selectbox("Filter Category:", ["All Emails", "Department Alias", "Direct Staff Email"])
    filtered_df = df if category_filter == "All Emails" else df[df['Category'] == category_filter]
    
    st.dataframe(filtered_df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("📋 Separated Email List (Click top-right icon to Copy)")
    
    email_list_str = "\n".join(filtered_df['Email Address'].tolist())
    st.code(email_list_str, language="text")
    
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Results as CSV",
        data=csv_data,
        file_name="domain_aliases.csv",
        mime="text/csv"
    )
