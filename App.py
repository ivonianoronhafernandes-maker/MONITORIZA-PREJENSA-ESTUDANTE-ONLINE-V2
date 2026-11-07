"""Grupo 1 Attendance - entry point.

Run with:  streamlit run App.py
           (Docker, Kafka and Spark are started automatically in the background)

Routing
  /?class=<token>   student check-in for one class (sidebar hidden)
  /                 admin pages (the dashboard itself is Flask: http://<host>:5000/dashboard)
"""
from __future__ import annotations

import streamlit as st

from src.core import browser, i18n
from src.core.config import BASE_DIR, settings

i18n.ensure()  # load the page modules in the saved language (Tetum / English / Indonesia); must come first
from src.data.database import init_db
from src.streaming import infrastructure
from src.streaming.runtime import start_pipeline
from src.ui import components as ui
from src.ui import shell
from src.ui.admin import (
    analytics_page, dashboard_page, records_page, reports_page, settings_page, students_page,
)
from src.ui.student import checkin_page

ASSETS = BASE_DIR / "assets"

st.set_page_config(page_title=settings.app_name, page_icon="🎓", layout="wide")
init_db()
infrastructure.start()  # once per server: bring up Docker, Kafka and Spark in the background
start_pipeline()  # once per server: backfill the event outbox and start the Kafka publisher
browser.flush_cookies()

checkin = st.Page(checkin_page.render, title=i18n.t("Check-in Estudante"), icon=":material/qr_code_scanner:",
                  url_path="checkin", default=True)

if st.query_params.get("class"):
    # Students coming from a class link only ever see the check-in page.
    navigation = st.navigation([checkin], position="hidden")
else:
    # No sign-in: the admin pages open directly (the dashboard is the home page at "/").
    # Sidebar = Dashboard, Students, Attendance, Analytics, Reports, Settings. Class links / QR codes
    # (formerly "Classes") now live under Settings > Classes.
    pages = {
        "students": st.Page(students_page.render, title=i18n.t("Estudante"), icon=":material/groups:", url_path="students", default=True),
        "attendance": st.Page(records_page.render, title=i18n.t("Prezensa"), icon=":material/event_available:", url_path="attendance"),
        "analytics": st.Page(analytics_page.render, title=i18n.t("Analiza"), icon=":material/bar_chart:", url_path="analytics"),
        "reports": st.Page(reports_page.render, title=i18n.t("Relatóriu"), icon=":material/description:", url_path="reports"),
        "settings": st.Page(settings_page.render, title=i18n.t("Konfigurasaun"), icon=":material/settings:", url_path="settings"),
    }
    shell.register_pages(pages)
    navigation = st.navigation(list(pages.values()))
    st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "icon.svg"), size="large")
    shell.sidebar_status()
    st.sidebar.link_button("Dashboard (Flask)", dashboard_page._flask_dashboard_url(), icon=":material/dashboard:")
    shell.topbar()

navigation.run()
