# 🧠 Cost Optimiser Agent (Beta)

> An AI-powered lightweight assistant to **reduce cloud costs** by automating actions like stopping and resuming high-cost services.  
> ⚠️ This is a **beta version** with many improvements in progress.

---

## ✨ Features

- 🔄 Automatically **stop or resume services** based on contextual understanding
- 👁️ **Display the current state** of all supported resources
- 📊 **Group resource status by type** (EC2, RDS, ASG)
- 🤖 Supports **semantic understanding** of user commands
- 🧭 Helps customers be **self-sufficient**, managing resources from one place

---

## ✅ Currently Supported Resources

| Resource Type | Supported Actions                     |
|---------------|----------------------------------------|
| EC2           | Stop / Start / Check State             |
| RDS           | Stop / Start / Check State             |
| ASG           | Scale In / Scale Out / Check State     |

- Shows both **running** and **stopped** services
- Resource states are **grouped by type**
- Individual resource state changes are under development

---

## 🔍 Examples

The agent understands various natural-language commands:

| Example Command                     | Action Performed                |
|-------------------------------------|---------------------------------|
| `"stop all running resources"`      | Stops EC2, scales in ASG, stops RDS |
| `"start stopped services"`          | Starts EC2, RDS; scales out ASG |
| `"show stopped services"`           | Displays all stopped resources |
| `"list running resources"`          | Lists all active resources     |

**Output is grouped by resource type** like:

```text
EC2:
- i-abc123 (running)
- i-def456 (stopped)

RDS:
- db-prod (running)
- db-test (stopped)

ASG:
- web-asg (2 instances running)
