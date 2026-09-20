import os
import hmac
import streamlit as st
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import plotly.express as px

# Optional OpenAI support
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# =========================================================
# PAGE SETUP
# =========================================================

st.set_page_config(
    page_title="FINREG AI",
    page_icon="🏦",
    layout="wide"
)

# =========================================================
# AUTHENTICATION
# =========================================================
# Demo authentication layer.
# Set these in PyCharm Run Configuration:
# FINREG_USERNAME=admin
# FINREG_PASSWORD=your_password
#
# For a production system, use a proper identity provider/database.

DEMO_USERNAME = os.getenv("FINREG_USERNAME", "admin")
DEMO_PASSWORD = os.getenv("FINREG_PASSWORD", "finreg123")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:

    st.title("🔐 FINREG AI")
    st.subheader("Secure Regulatory Intelligence Portal")
    st.write("Please sign in to access the FINREG dashboard.")

    with st.form("login_form"):
        username = st.text_input(
            "Username",
            placeholder="Enter username"
        )

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password"
        )

        login_clicked = st.form_submit_button(
            "🔓 Sign In",
            type="primary",
            use_container_width=True
        )

    if login_clicked:
        username_ok = hmac.compare_digest(
            username,
            DEMO_USERNAME
        )
        password_ok = hmac.compare_digest(
            password,
            DEMO_PASSWORD
        )

        if username_ok and password_ok:
            st.session_state.authenticated = True
            st.session_state.login_user = username
            st.rerun()
        else:
            st.error("❌ Invalid username or password.")

    st.info(
        "FINREG AI is a prototype. Authentication is included "
        "for demonstration purposes."
    )

    st.stop()

st.title("🏦 FINREG AI")
st.subheader("AI Financial Regulation Radar")
st.write(
    "An early-warning dashboard for identifying potential financial "
    "regulatory risks, ecosystem dependencies, and areas for human review."
)


# =========================================================
# LOAD DATA
# =========================================================

try:
    companies = pd.read_csv("companies.csv")
    regulations = pd.read_csv("regulations.csv")
    relationships = pd.read_csv("relationships.csv")
except FileNotFoundError as e:
    st.error(f"Missing file: {e.filename}")
    st.info(
        "Make sure companies.csv, regulations.csv and relationships.csv "
        "are in the same folder as app.py."
    )
    st.stop()


# Make the app work with either "country" or "jurisdiction"
reg_country_column = (
    "country" if "country" in regulations.columns
    else "jurisdiction" if "jurisdiction" in regulations.columns
    else None
)

if reg_country_column is None:
    st.error(
        "regulations.csv needs a 'country' or 'jurisdiction' column."
    )
    st.stop()


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("⚙️ FINREG Controls")

st.sidebar.success(
    f"👤 Signed in as: {st.session_state.get('login_user', 'User')}"
)

if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.pop("login_user", None)
    st.rerun()

st.sidebar.divider()

selected_company = st.sidebar.selectbox(
    "🏢 Select company",
    companies["name"].tolist()
)

company = companies[
    companies["name"] == selected_company
].iloc[0]

st.sidebar.divider()
st.sidebar.write("### 🎛️ What-if Simulator")

simulate_behavioral = st.sidebar.checkbox(
    "Uses Behavioral Data",
    value="Behavioral Data" in str(company["data_sources"])
)

simulate_device = st.sidebar.checkbox(
    "Uses Device Data",
    value="Device Data" in str(company["data_sources"])
)

simulate_ai = st.sidebar.checkbox(
    "Uses AI",
    value="AI" in str(company["products"])
)

simulate_cross_border = st.sidebar.checkbox(
    "Cross-Border Activity",
    value="Cross Border" in str(company["products"])
)

simulate_payments = st.sidebar.checkbox(
    "Payment Activity",
    value="Payment" in str(company["products"])
)

simulate_large_customer_base = st.sidebar.checkbox(
    "5M+ Customers",
    value=int(company["customers"]) >= 5_000_000
)


# =========================================================
# DASHBOARD KPIs
# =========================================================

st.divider()
st.header("📊 Regulatory Intelligence Dashboard")

# These are prototype indicators, not legal determinations.
active_signals = sum([
    simulate_behavioral,
    simulate_device,
    simulate_ai,
    simulate_cross_border,
    simulate_payments,
    simulate_large_customer_base
])

relationship_count = len(
    relationships[
        (relationships["source"] == selected_company) |
        (relationships["target"] == selected_company)
    ]
)

k1, k2, k3, k4 = st.columns(4)

k1.metric("Companies Monitored", len(companies))
k2.metric("Active Risk Signals", active_signals)
k3.metric("Ecosystem Connections", relationship_count)
k4.metric("Regulatory Frameworks", len(regulations))


# =========================================================
# COMPANY OVERVIEW
# =========================================================

st.header("🏢 Company Overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Company", company["name"])
col2.metric("Type", company["type"])
col3.metric("Country", company["country"])
col4.metric("Customers", f"{int(company['customers']):,}")

st.write("### Products")
st.info(company["products"])

st.write("### Data Sources")
for source in str(company["data_sources"]).split(";"):
    st.write("•", source)


# =========================================================
# RISK ENGINE
# =========================================================

risks = {
    "Consumer Protection": 1,
    "Data Privacy": 1,
    "Competition": 1,
    "Financial Stability": 1,
    "Cross-Border": 1,
    "Cybersecurity": 1,
    "AI Governance": 1
}

if simulate_behavioral or simulate_device:
    risks["Data Privacy"] = 3

if simulate_ai:
    risks["AI Governance"] = 3
    risks["Consumer Protection"] = 2

if simulate_cross_border:
    risks["Cross-Border"] = 3

if simulate_large_customer_base:
    risks["Competition"] = 2

if simulate_payments:
    risks["Cybersecurity"] = 2


def risk_level(score):
    if score == 3:
        return "HIGH"
    if score == 2:
        return "MEDIUM"
    return "LOW"


def risk_icon(score):
    if score == 3:
        return "🔴"
    if score == 2:
        return "🟠"
    return "🟢"


# =========================================================
# RISK RADAR
# =========================================================

st.divider()
st.header("🚨 Regulatory Risk Radar")
st.write(
    "Risk signals highlight areas that may warrant additional "
    "investigation. They are not automatic legal conclusions."
)

risk_columns = st.columns(len(risks))

for column, (risk, score) in zip(risk_columns, risks.items()):
    column.metric(
        risk,
        f"{risk_icon(score)} {risk_level(score)}"
    )

categories = list(risks.keys())
values = list(risks.values())

fig_radar = go.Figure()

fig_radar.add_trace(
    go.Scatterpolar(
        r=values + values[:1],
        theta=categories + categories[:1],
        fill="toself",
        name="Risk Signal"
    )
)

fig_radar.update_layout(
    polar=dict(
        radialaxis=dict(
            visible=True,
            range=[0, 3],
            tickvals=[1, 2, 3],
            ticktext=["Low", "Medium", "High"]
        )
    ),
    showlegend=False,
    height=500
)

st.plotly_chart(fig_radar, use_container_width=True)


# =========================================================
# RISK BREAKDOWN
# =========================================================

st.header("🧠 Risk Explanation")

risk_reasons = {
    "Data Privacy":
        "Behavioral or device data can create additional questions around "
        "data collection, processing, protection and user transparency.",

    "AI Governance":
        "AI-based financial systems may warrant review of transparency, "
        "governance, explainability and monitoring controls.",

    "Consumer Protection":
        "AI or digital financial products may create questions around "
        "customer transparency, disclosures and potential customer impact.",

    "Competition":
        "A large customer base can be a signal for examining market "
        "concentration and ecosystem dependencies.",

    "Cross-Border":
        "Cross-border activity may involve additional jurisdictions and "
        "coordination between regulatory frameworks.",

    "Cybersecurity":
        "Payment activity can increase the importance of cybersecurity "
        "and operational-resilience controls.",

    "Financial Stability":
        "Financial infrastructure dependencies can be examined for "
        "potential concentration or operational dependency."
}

for risk, score in risks.items():
    if score >= 2:
        if score == 3:
            st.error(
                f"{risk_icon(score)} **{risk}: {risk_level(score)}**\n\n"
                f"{risk_reasons[risk]}"
            )
        else:
            st.warning(
                f"{risk_icon(score)} **{risk}: {risk_level(score)}**\n\n"
                f"{risk_reasons[risk]}"
            )


# =========================================================
# RISK BAR CHART
# =========================================================

st.subheader("📈 Risk Signal Comparison")

risk_df = pd.DataFrame({
    "Risk Area": categories,
    "Score": values
})

fig_bar = px.bar(
    risk_df,
    x="Risk Area",
    y="Score",
    range_y=[0, 3.5],
    text="Score"
)

fig_bar.update_layout(
    height=400,
    yaxis=dict(
        tickvals=[1, 2, 3],
        ticktext=["Low", "Medium", "High"]
    )
)

st.plotly_chart(fig_bar, use_container_width=True)


# =========================================================
# ALERT CENTER
# =========================================================

st.divider()
st.header("🚨 Regulatory Alert Center")

high_alerts = [
    risk for risk, score in risks.items()
    if score == 3
]

medium_alerts = [
    risk for risk, score in risks.items()
    if score == 2
]

if high_alerts:
    st.error(
        f"🔴 {len(high_alerts)} high-level signal(s): "
        + ", ".join(high_alerts)
    )

if medium_alerts:
    st.warning(
        f"🟠 {len(medium_alerts)} medium-level signal(s): "
        + ", ".join(medium_alerts)
    )

if not high_alerts and not medium_alerts:
    st.success("🟢 No elevated prototype risk signals detected.")


# =========================================================
# REGULATORY FRAMEWORKS
# =========================================================

st.divider()
st.header("📜 Relevant Regulatory Frameworks")

company_country = company["country"]

relevant_regulations = regulations[
    regulations[reg_country_column].astype(str).str.lower()
    == str(company_country).lower()
]

if len(relevant_regulations) == 0:
    st.info("No matching regulatory frameworks found.")
else:
    for _, regulation in relevant_regulations.iterrows():
        with st.expander(
            f"📜 {regulation['name']} — {regulation['topic']}"
        ):
            st.write(regulation["description"])


# =========================================================
# AI REGULATORY ASSISTANT
# =========================================================

st.divider()
st.header("🤖 AI Regulatory Assistant")

st.write(
    "Ask questions about the selected company, its risk signals, "
    "or areas that may warrant human review."
)

question = st.text_input(
    "💬 Ask FINREG AI",
    placeholder="Why is this company considered high risk?"
)

if st.button("🤖 Analyze with AI", type="primary"):

    if not question:
        st.warning("Please enter a question first.")

    elif OpenAI is None:
        st.error("The OpenAI package is not installed.")
        st.code("python3 -m pip install openai")

    elif not os.getenv("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY is not connected.")
        st.info(
            "Add OPENAI_API_KEY to your PyCharm Run Configuration "
            "environment variables."
        )

    else:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        risk_text = "\n".join(
            f"- {risk}: {risk_level(score)}"
            for risk, score in risks.items()
        )

        prompt = f"""
You are FINREG AI, a financial regulatory intelligence assistant.

This is a fictional prototype using synthetic company and regulatory data.

Company:
{company['name']}

Type:
{company['type']}

Country:
{company['country']}

Customers:
{company['customers']}

Products:
{company['products']}

Data Sources:
{company['data_sources']}

Risk signals:
{risk_text}

User question:
{question}

Give a concise, structured answer.

Use phrases such as:
- potential risk
- possible concern
- may warrant review

Do not claim that the company broke a law.
Do not declare the company illegal or compliant.
Recommend human review where appropriate.
"""

        with st.spinner("🤖 FINREG AI is analyzing..."):
            try:
                response = client.responses.create(
                    model="gpt-5.6-luna",
                    input=prompt
                )

                st.success("AI Analysis")
                st.markdown(response.output_text)

            except Exception as e:
                st.error(f"AI request failed: {e}")


# =========================================================
# FINANCIAL ECOSYSTEM
# =========================================================

st.divider()
st.header("🕸️ Financial Ecosystem")

company_relationships = relationships[
    (relationships["source"] == selected_company) |
    (relationships["target"] == selected_company)
]

if len(company_relationships) > 0:
    st.dataframe(
        company_relationships,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No relationships found.")


# =========================================================
# NETWORK GRAPH
# =========================================================

G = nx.Graph()

for _, row in relationships.iterrows():
    G.add_edge(row["source"], row["target"])

nodes = {selected_company}

if selected_company in G:
    for neighbor in G.neighbors(selected_company):
        nodes.add(neighbor)

subgraph = G.subgraph(nodes)

if len(subgraph.nodes) > 1:

    positions = nx.spring_layout(
        subgraph,
        seed=42
    )

    edge_x = []
    edge_y = []

    for source, target in subgraph.edges():
        x0, y0 = positions[source]
        x1, y1 = positions[target]

        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        hoverinfo="none",
        line=dict(width=2)
    )

    node_x = []
    node_y = []
    node_text = []

    for node in subgraph.nodes():
        x, y = positions[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="top center",
        marker=dict(size=25),
        hoverinfo="text"
    )

    graph_fig = go.Figure(
        data=[edge_trace, node_trace]
    )

    graph_fig.update_layout(
        height=550,
        showlegend=False,
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False
        )
    )

    st.plotly_chart(
        graph_fig,
        use_container_width=True
    )


# =========================================================
# DATA QUALITY
# =========================================================

st.divider()
st.header("🔍 Data Quality Check")

quality_checks = {
    "Company data available": not company.empty,
    "Company country available": bool(str(company["country"]).strip()),
    "Products available": bool(str(company["products"]).strip()),
    "Data sources available": bool(str(company["data_sources"]).strip()),
    "Regulatory data available": len(relevant_regulations) > 0,
    "Relationship data available": len(company_relationships) > 0
}

for check, passed in quality_checks.items():
    if passed:
        st.write(f"✅ {check}")
    else:
        st.write(f"⚠️ {check}")


# =========================================================
# DOWNLOAD REPORT
# =========================================================

st.divider()
st.header("📥 Export Regulatory Snapshot")

report = pd.DataFrame({
    "Company": [company["name"]] * len(risks),
    "Risk Area": list(risks.keys()),
    "Risk Level": [risk_level(v) for v in risks.values()],
    "Score": list(risks.values())
})

csv_report = report.to_csv(index=False)

st.download_button(
    label="📥 Download Risk Report (CSV)",
    data=csv_report,
    file_name=f"{selected_company}_risk_report.csv",
    mime="text/csv"
)


# =========================================================
# HUMAN REVIEW
# =========================================================

st.divider()
st.header("👤 Human Review")

st.info(
    "FINREG AI is an early-warning and decision-support prototype. "
    "Risk signals are intended to support human investigation and "
    "do not represent automatic legal or regulatory conclusions."
)

st.caption(
    "FINREG AI • Financial Regulatory Intelligence Prototype • "
    "Synthetic demonstration data"
)
