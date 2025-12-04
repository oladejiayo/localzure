# 🌀 LocalZure

### *The complete local Azure cloud stack for rapid development & testing — offline, fast, free.*

LocalZure is an open-source platform that emulates major **Microsoft Azure cloud services** on your local machine. It provides a fully local Azure-compatible environment so you can develop, test, and prototype cloud applications **without deploying to Azure**, **without internet connectivity**, and **without incurring any cloud costs**.

LocalZure aims to do for Azure what LocalStack does for AWS:

> **Deliver a high-fidelity, production-like local cloud that "just works" with your existing Azure SDKs, IaC tools, and workflows.**

---

## 🚀 Key Features

### 🔹 Local Azure Cloud

Run popular Azure services locally, including:

* **Blob Storage** (via enhanced Azurite backend)
* **Queue Storage**
* **Table Storage**
* **Service Bus** (AMQP 1.0 compatible emulator)
* **Key Vault** (mock secure secrets store)
* **Event Grid** (local event routing & webhook dispatch)
* **Cosmos DB** (DocumentDB/NoSQL local emulator)
* **App Configuration**
* **Azure Functions Runtime** (trigger simulation, Core Tools integration)

More services are added over time through a modular plugin system.

---

## 🧩 Why LocalZure?

### ⚡ Faster cloud development

No more waiting for deployments, provisioning, or network calls. Your cloud logic runs instantly on localhost.

### 💸 Zero cost

Run your full Azure architecture locally with no Azure subscription required.

### 🛠 Transparent integration

LocalZure is designed as a **drop-in replacement** for Azure endpoints.
Your existing Azure SDK code can run against LocalZure with minimal or no changes.

### 🔧 Built for Devs & CI/CD

Perfect for:

* Local development
* Automated tests
* Offline prototyping
* Continuous Integration pipelines
* Teaching cloud engineering
* Reproducing production issues

---

## 🏗 Architecture Overview

LocalZure consists of:

### **1. LocalZure Core**

A Python-powered control plane that:

* Routes API requests
* Manages containerized service emulators
* Maps Azure endpoints to local equivalents
* Exposes a unified CLI
* Provides a plugin system for new services

### **2. Service Emulation Layer**

Each Azure service is implemented as a standalone module or container.
Examples:

* Storage → uses extended **Azurite**
* Service Bus → lightweight AMQP server
* Key Vault → Python microservice with encrypted storage
* Event Grid → event router + topic/subscription handlers

### **3. Docker-based Orchestration**

LocalZure runs services either:

* Directly on the host, or
* Via Docker containers (recommended)

---

## 🏁 Getting Started

### 📦 Installation

```bash
pip install localzure
```

Alternatively, install via Homebrew (coming soon):

```bash
brew install localzure
```

Or clone and run locally:

```bash
git clone https://github.com/<your-org>/localzure.git
cd localzure
make install
```

---

## ▶️ Quick Start

Start the local Azure stack:

```bash
localzure start
```

Check running services:

```bash
localzure status
```

Stop everything:

```bash
localzure stop
```

View logs:

```bash
localzure logs
```

---

## 🔌 Using with Azure SDKs

Update your environment variables to point Azure SDKs to LocalZure:

```bash
export AZURE_STORAGE_BLOB_ENDPOINT=http://localhost:10000
export AZURE_SERVICEBUS_ENDPOINT=http://localhost:5672
export AZURE_KEYVAULT_ENDPOINT=http://localhost:8200
```

Use the standard Azure SDK in your code — no changes required:

```python
from azure.storage.blob import BlobServiceClient

client = BlobServiceClient.from_connection_string(
    "UseDevelopmentStorage=true"
)
```

---

## 📡 Supported Services (MVP)

| Azure Service     | Status | Notes                     |
| ----------------- | ------ | ------------------------- |
| Blob Storage      | ✅      | Enhanced Azurite          |
| Queue Storage     | ✅      | Azurite                   |
| Table Storage     | ✅      | Azurite                   |
| Service Bus       | 🚧     | AMQP 1.0 emulator         |
| Key Vault         | 🚧     | Local secrets store       |
| Event Grid        | 🚧     | Local event router        |
| Cosmos DB         | 🚧     | DocumentDB local emulator |
| App Configuration | 🚧     | JSON + memory backend     |
| Azure Functions   | 🚧     | Core Tools integration    |

Additional services will be introduced via plugins.

---

## ⚙️ Configuration

Create a `localzure.yml`:

```yaml
services:
  blob:
    enabled: true
  servicebus:
    port: 5672
  keyvault:
    storage_path: .localzure/keyvault
  cosmos:
    backend: sqlite
  eventgrid:
    delivery_retries: 5

logging:
  level: info
```

Run:

```bash
localzure start --config localzure.yml
```

---

## 🔌 Plugin System

LocalZure supports a flexible plugin model:

* Add new Azure service emulators
* Replace internal modules with custom implementations
* Run containers, Python processes, or external binaries

Example plugin declaration:

```yaml
plugins:
  custom-search-emulator:
    path: ./plugins/search
```

---

## 🧪 Testing

LocalZure integrates with:

* pytest
* unittest
* GitHub Actions / GitLab CI
* Terraform tests
* Bicep deployments
* Pulumi

Example:

```bash
pytest --localzure
```

---

## 🛡 License

LocalZure is released under the **Apache License 2.0**, the same as LocalStack.

---

## 🤝 Contributing

Contributions are welcome!
Please read the contributing guide and open a PR.

Ways to help:

* Implement new Azure service emulators
* Improve SDK compatibility
* Extend the CLI
* Write docs and examples
* Test Windows/Linux/Mac compatibility

---

## 🌐 Community & Support

* GitHub Issues — bug reports and feature requests
* GitHub Discussions — Q&A, idea sharing
* Discord/Slack — coming soon
* Releases — versioned and changelog maintained

---

## ⭐ Roadmap Overview (High Level Only)

* Core runtime v1.0
* 10–15 Azure services supported
* Terraform & Pulumi integration
* Full CLI dashboard
* Plugin marketplace
* Declarative environment specs

---

## 🌟 Star the Repo

If LocalZure helps you, please consider starring the repository — it helps grow the community and attract contributors!

 

Just tell me what you'd like next.
 
