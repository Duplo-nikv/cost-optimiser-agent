# 🧠 Cost Optimiser Agent (Beta)

> A lightweight, AI-powered agent to help **reduce cloud costs** by automating the stopping and resuming of high-cost services.  
> ⚠️ Currently in **beta** – lots of improvements are planned!

---

## ✨ Features

- 🚦 **Stop and Resume Services** based on cost-impact analysis  
- ⚙️ Supports major AWS services: **RDS**, **ASG**, and **EC2**
- 🗣️ Semantic command understanding (e.g., "stop running services" → stop operation)

---

## 📦 Currently Supported Resources

| Resource Type | Actions Supported          |
|---------------|-----------------------------|
| EC2           | Stop / Start                |
| RDS           | Stop / Start                |
| ASG           | Scale In (stop) / Scale Out (resume) |

---

## ⚙️ How It Works

The agent interprets operational commands and maps them to cost-saving actions. For example:

- 🔴 `"stop all running resources"` → Stops active EC2, pauses ASG, and stops RDS
- 🟢 `"start stopped services"` → Resumes stopped EC2, reactivates ASG, and starts RDS

---

## 🚧 Limitations (Beta)

- 🧠 Semantic resolution is improving – may not cover all phrasings
- 💰 No real-time billing data integration (yet)
- 🌐 Supports AWS only (multi-cloud support in pipeline)

---

## 🚀 Getting Started

```bash
git clone https://github.com/your-org/cost-optimiser-agent.git
cd cost-optimiser-agent
docker-compose up --build
