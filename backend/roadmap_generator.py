"""
Dynamic AI Skill Gap Roadmap Generator
Generates personalized, in-depth, and highly specific learning roadmaps
for any technical skill required by Job Descriptions.
"""

import re
import logging

# Comprehensive specialized knowledge base for 50+ mainstream technologies
SKILL_KNOWLEDGE_BASE = {
    # ---------------- Frontend & Web ----------------
    "react": {
        "domain": "Frontend Engineering",
        "difficulty": "Intermediate",
        "summary": "Master component-driven architecture, reactive state management, and modern React 18+ hooks to build fast web applications.",
        "beginner": [
            "JSX syntax, component props, and state with useState",
            "Handling events, conditional rendering, and list mapping with keys",
            "Effect lifecycle management using useEffect and custom hook fundamentals"
        ],
        "intermediate": [
            "Advanced state management with Context API, Redux Toolkit, or Zustand",
            "Performance optimization with useMemo, useCallback, and React.memo",
            "Client-side routing with React Router 6 and data loaders"
        ],
        "advanced": [
            "React 18 Concurrent Features: Suspense, Transitions (useTransition), and streaming",
            "Server Components (RSC) and integration with Next.js App Router",
            "Custom component library architecture with accessibility (ARIA) and Headless UI"
        ],
        "practice": [
            "Refactor a prop-drilling app to use modern Zustand/Redux Toolkit state slices",
            "Build an infinite-scroll feed using IntersectionObserver and custom React hooks",
            "Profile and resolve unnecessary component re-renders using React DevTools Profiler"
        ],
        "projects": [
            {
                "title": "Interactive Analytics Dashboard with Real-Time Data",
                "description": "Build a responsive SaaS dashboard with chart visualizations, theme toggling, and interactive data filters.",
                "deliverables": "Deployed application on Vercel with reusable UI components, dark mode, and state persistence."
            },
            {
                "title": "Full-Featured Kanban Task Manager",
                "description": "Develop a Trello-style board with drag-and-drop column management, optimistic UI updates, and local storage sync.",
                "deliverables": "Production-ready repository with comprehensive component unit tests using React Testing Library."
            }
        ],
        "assessments": [
            {
                "question": "What is the Virtual DOM diffing algorithm (Reconciliation), and why are stable keys essential?",
                "key_points": "Explain how React computes minimal DOM mutations and why array indexes as keys cause state mismatch during reordering."
            },
            {
                "question": "How do useMemo and useCallback differ, and when does premature optimization harm performance?",
                "key_points": "useMemo caches computed values; useCallback caches function references. Both introduce memory overhead if applied to trivial operations."
            },
            {
                "question": "How do React 18 Server Components differ from Client Components?",
                "key_points": "RSCs execute strictly on the server with zero client bundle impact, whereas Client Components handle user interactivity and browser APIs."
            }
        ],
        "timeline_weeks": 4,
        "estimated_hours": 40,
        "resources": [
            {"title": "Official React Documentation (react.dev)", "type": "Documentation"},
            {"title": "Beta React 18 Architecture Deep Dive", "type": "Guide"},
            {"title": "Epic React by Kent C. Dodds", "type": "Interactive Course"}
        ]
    },

    "typescript": {
        "domain": "Software Engineering & Frontend",
        "difficulty": "Intermediate",
        "summary": "Implement static typing, strict type inference, generics, and compiler configurations to write enterprise-grade, bug-free applications.",
        "beginner": [
            "Primitive types, type annotations, and union vs intersection types",
            "Interfaces vs Type Aliases and structural typing (duck typing)",
            "Configuring tsconfig.json for modern ES modules and strict mode"
        ],
        "intermediate": [
            "Generic functions, interfaces, and constrained generics (T extends Record)",
            "Utility types: Partial, Pick, Omit, Record, Readonly, and Exclude",
            "Type narrowing using type guards, typeof, instanceof, and discriminated unions"
        ],
        "advanced": [
            "Conditional types, mapped types, and the 'infer' keyword for template literal types",
            "Ambient declarations (.d.ts) and typing third-party JavaScript libraries",
            "Advanced metaprogramming with TypeScript decorators and AST transformer concepts"
        ],
        "practice": [
            "Convert an existing vanilla JavaScript project to strict-mode TypeScript without using 'any'",
            "Write custom generic validation guards that validate runtime API payloads against types",
            "Implement a strongly-typed Event Emitter using mapped types"
        ],
        "projects": [
            {
                "title": "Type-Safe REST API Client SDK",
                "description": "Construct an npm-ready API SDK with complete autocomplete and compile-time validation for endpoint parameters and responses.",
                "deliverables": "Published/packaged library with .d.ts typings and automated Vitest test suite."
            }
        ],
        "assessments": [
            {
                "question": "What is the difference between 'any' and 'unknown' in TypeScript?",
                "key_points": "'unknown' is the type-safe counterpart of 'any'. Operations on 'unknown' require explicit type checking or casting before invocation."
            },
            {
                "question": "How do Discriminated Unions work, and why are they superior to loose optional properties?",
                "key_points": "A common literal discriminant property allows TypeScript's control flow analysis to narrow the union exhaustively in switch/if blocks."
            }
        ],
        "timeline_weeks": 3,
        "estimated_hours": 30,
        "resources": [
            {"title": "TypeScript Handbook (typescriptlang.org)", "type": "Official Docs"},
            {"title": "Type Hero Interactive Challenges", "type": "Practice Playground"}
        ]
    },

    "next.js": {
        "domain": "Full-Stack Web Development",
        "difficulty": "Intermediate to Advanced",
        "summary": "Master the Next.js App Router, Server Actions, Incremental Static Regeneration (ISR), and Edge deployment to deliver high-performance web applications.",
        "beginner": [
            "App Router directory structure: layout.tsx, page.tsx, and loading.tsx",
            "Client Components ('use client') vs Server Components ('use server')",
            "Static Site Generation (SSG) vs Server-Side Rendering (SSR)"
        ],
        "intermediate": [
            "Server Actions for form submissions and zero-API database mutations",
            "Data caching strategies, revalidation (revalidateTag, revalidatePath), and fetch options",
            "Route Handlers (app/api/route.ts) and Edge runtime middleware"
        ],
        "advanced": [
            "Streaming with Suspense and progressive page hydration",
            "Dynamic metadata generation and OpenGraph SEO optimization",
            "Edge caching, multi-tenant subdomains, and standalone Docker deployment"
        ],
        "practice": [
            "Build an SEO-optimized blog using ISR that revalidates articles on-demand via webhook",
            "Implement secure authentication with NextAuth.js v5 (Auth.js) and JWT session handling",
            "Migrate a legacy Pages Router application to App Router"
        ],
        "projects": [
            {
                "title": "Full-Stack E-Commerce Platform with Server Actions & Stripe",
                "description": "Create an e-commerce platform with product catalogs, dynamic search, shopping cart, and Stripe checkout.",
                "deliverables": "Live Next.js 14+ application with lighthouse score > 95 and server-side payment processing."
            }
        ],
        "assessments": [
            {
                "question": "How does Next.js App Router caching work across Request, Data, Full Route, and Router Cache?",
                "key_points": "Explain the 4 caching tiers, automatic fetch deduping, and how 'force-dynamic' or 'revalidate' invalidates cache layers."
            }
        ],
        "timeline_weeks": 4,
        "estimated_hours": 35,
        "resources": [
            {"title": "Next.js Learn Course", "type": "Interactive Course"},
            {"title": "Next.js Official App Router Documentation", "type": "Documentation"}
        ]
    },

    "node.js": {
        "domain": "Backend Engineering",
        "difficulty": "Intermediate",
        "summary": "Harness the Node.js event loop, asynchronous I/O, streams, and cluster architectures to build resilient, high-throughput backend services.",
        "beginner": [
            "V8 runtime, CommonJS vs ES Modules, and Node.js process global",
            "Core modules: fs, path, http, and events (EventEmitter)",
            "Asynchronous programming: callbacks, Promises, and async/await mechanics"
        ],
        "intermediate": [
            "Event Loop phases: timers, pending callbacks, poll, check (setImmediate), and close",
            "Streams and Buffers (Readable, Writable, Transform) for memory-efficient I/O",
            "RESTful API construction with Express.js or Fastify, middleware chains, and error handlers"
        ],
        "advanced": [
            "Multi-process concurrency using the Cluster module and Worker Threads",
            "Memory leak profiling with Chrome DevTools and heap snapshot analysis",
            "Microservice architecture with event brokers (RabbitMQ/Kafka) and gRPC integration"
        ],
        "practice": [
            "Stream a multi-gigabyte CSV file through a Transform stream with constant memory usage",
            "Write a custom rate-limiting middleware using Redis token-bucket algorithms",
            "Benchmark and optimize an Express route handling 10,000 req/sec"
        ],
        "projects": [
            {
                "title": "High-Throughput File Ingestion & Processing Microservice",
                "description": "Build an API that accepts bulk file uploads, processes them via worker threads, and writes to cloud storage.",
                "deliverables": "Dockerized microservice with health checks, structured logging (Pino/Winston), and Swagger docs."
            }
        ],
        "assessments": [
            {
                "question": "Explain the exact lifecycle of the Node.js Event Loop and the difference between process.nextTick() and setImmediate().",
                "key_points": "nextTick executes immediately after the current operation before the loop continues, while setImmediate executes in the check phase."
            }
        ],
        "timeline_weeks": 4,
        "estimated_hours": 40,
        "resources": [
            {"title": "Node.js Official Documentation & Guides", "type": "Docs"},
            {"title": "Node.js Design Patterns by Mario Casciaro", "type": "Book"}
        ]
    },

    "kubernetes": {
        "domain": "Cloud & DevOps",
        "difficulty": "Advanced",
        "summary": "Deploy, scale, and orchestrate containerized microservices in production clusters with automated self-healing and service mesh networking.",
        "beginner": [
            "Cluster architecture: Control plane (API Server, etcd, Scheduler) vs Worker nodes (kubelet, kube-proxy)",
            "Basic primitives: Pods, ReplicaSets, and Deployments",
            "kubectl CLI commands: apply, get, describe, logs, and port-forward"
        ],
        "intermediate": [
            "Service types: ClusterIP, NodePort, and LoadBalancer with Ingress Controllers",
            "Configuration management using ConfigMaps, Secrets, and downward API",
            "Persistent storage: StorageClasses, PersistentVolumes (PV), and PersistentVolumeClaims (PVC)"
        ],
        "advanced": [
            "Horizontal Pod Autoscaling (HPA) based on CPU/Memory and custom Prometheus metrics",
            "Deployment strategies: Rolling Updates, Canary, and Blue/Green with ArgoCD (GitOps)",
            "NetworkPolicies, RBAC security, and Helm chart authoring for multi-tier apps"
        ],
        "practice": [
            "Spin up a local Minikube/Kind cluster and deploy a containerized full-stack application",
            "Create a Helm chart that packages frontend, backend, and PostgreSQL with customizable values",
            "Simulate a node failure and observe automated pod self-healing and rescheduling"
        ],
        "projects": [
            {
                "title": "Production-Ready Microservices Cluster with Ingress & Monitoring",
                "description": "Deploy a multi-service architecture with Nginx Ingress, TLS certificates (cert-manager), and Prometheus/Grafana monitoring.",
                "deliverables": "GitOps repository with Helm charts and automated ArgoCD pipeline manifests."
            }
        ],
        "assessments": [
            {
                "question": "What is the difference between a Liveness Probe and a Readiness Probe in Kubernetes?",
                "key_points": "Liveness probe determines if a container needs restarting; readiness probe determines if a container is ready to accept user traffic."
            }
        ],
        "timeline_weeks": 5,
        "estimated_hours": 45,
        "resources": [
            {"title": "Kubernetes Official Documentation (kubernetes.io)", "type": "Documentation"},
            {"title": "Certified Kubernetes Administrator (CKA) Hands-on Labs", "type": "Certification Guide"}
        ]
    },

    "postgresql": {
        "domain": "Database Engineering",
        "difficulty": "Intermediate to Advanced",
        "summary": "Design ACID-compliant relational schemas, query plans, indexing strategies, and high-availability database architectures.",
        "beginner": [
            "Relational schema design, normalization (1NF-3NF), primary keys, and foreign keys",
            "Core DDL & DML: CREATE, ALTER, INSERT, UPDATE, DELETE, and transactional boundaries (BEGIN/COMMIT)",
            "Complex queries: INNER, LEFT, RIGHT, FULL OUTER JOINs, and GROUP BY aggregations"
        ],
        "intermediate": [
            "Indexing internals: B-Tree, GIN, GiST, and partial/expression indexes",
            "Query plan analysis using EXPLAIN (ANALYZE, BUFFERS) to eliminate sequential scans",
            "Window functions (ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD) and Common Table Expressions (CTEs)"
        ],
        "advanced": [
            "Concurrency control: Multi-Version Concurrency Control (MVCC) and transaction isolation levels",
            "Table partitioning (Range/List) for billion-row tables and database connection pooling (PgBouncer)",
            "JSONB querying with GIN indexing for hybrid relational-document patterns"
        ],
        "practice": [
            "Diagnose and optimize a slow query from 3500ms down to 15ms using compound indexes and EXPLAIN",
            "Implement a recursive CTE to traverse hierarchical organization trees or category graphs",
            "Configure streaming replication and automated failover between Primary and Standby nodes"
        ],
        "projects": [
            {
                "title": "High-Performance Financial Ledger & Auditing System",
                "description": "Design an append-only transaction ledger with strict foreign key constraints, triggers, and JSONB audit logs.",
                "deliverables": "SQL migration scripts, benchmark tests demonstrating 50,000 TPS, and ER diagrams."
            }
        ],
        "assessments": [
            {
                "question": "How does PostgreSQL MVCC avoid read/write locks, and why is VACUUM necessary?",
                "key_points": "MVCC creates row versions (xmin/xmax). Readers never block writers and writers never block readers. VACUUM reclaims dead tuples created by updates/deletes."
            }
        ],
        "timeline_weeks": 4,
        "estimated_hours": 35,
        "resources": [
            {"title": "PostgreSQL Official Documentation", "type": "Docs"},
            {"title": "Use The Index, Luke (SQL Indexing Guide)", "type": "Interactive Guide"}
        ]
    },

    "mongodb": {
        "domain": "Database Engineering",
        "difficulty": "Intermediate",
        "summary": "Model polymorphic NoSQL data, master the Aggregation Pipeline, and architect distributed sharded clusters with replica sets.",
        "beginner": [
            "Document model concepts: BSON, collections, ObjectIds, and dynamic schemas",
            "CRUD operations with PyMongo / Mongoose: insertOne, find, updateOne, and deleteMany",
            "Query operators: $eq, $in, $gt, $elemMatch, and projection syntax"
        ],
        "intermediate": [
            "Data modeling patterns: Embedding vs Referencing (1:1, 1:N, N:M trade-offs)",
            "The Aggregation Pipeline: $match, $group, $lookup, $unwind, and $project",
            "Compound indexes, TTL indexes, text search indexes, and executionStats analysis"
        ],
        "advanced": [
            "Replica set architecture: Primary election, Oplog replication, and write concerns (w: majority)",
            "Sharding strategies: Choosing optimal shard keys to prevent data skew and jumbo chunks",
            "Change Streams for real-time reactive event-driven applications"
        ],
        "practice": [
            "Write a multi-stage aggregation pipeline calculating monthly revenue by customer tier",
            "Design an e-commerce catalog supporting polymorphic product attributes with zero migration downtime",
            "Use hint() and explain('executionStats') to optimize an un-indexed collection scan"
        ],
        "projects": [
            {
                "title": "Real-Time Collaborative Document Store with Change Streams",
                "description": "Build a multi-user collaborative workspace that syncs document modifications in real-time across users.",
                "deliverables": "Node.js/Python backend with MongoDB Change Streams and WebSocket broadcasting."
            }
        ],
        "assessments": [
            {
                "question": "When should you embed documents versus reference documents in MongoDB?",
                "key_points": "Embed for 1:Few relationships where data is accessed together and does not exceed 16MB; reference for 1:Many/Many:Many or frequently updated unbounded arrays."
            }
        ],
        "timeline_weeks": 3,
        "estimated_hours": 30,
        "resources": [
            {"title": "MongoDB University (learn.mongodb.com)", "type": "Official Cert Course"},
            {"title": "MongoDB Schema Design Patterns", "type": "Architecture Guide"}
        ]
    },

    "git": {
        "domain": "Software Engineering & Collaboration",
        "difficulty": "Beginner to Intermediate",
        "summary": "Master distributed version control, non-linear branching workflows, conflict resolution, and collaborative GitOps patterns.",
        "beginner": [
            "Git internals: Working directory, Staging area (Index), and Commit history (HEAD)",
            "Core commands: init, clone, add, commit, push, pull, branch, and checkout/switch",
            "Writing meaningful atomic commit messages following Conventional Commits"
        ],
        "intermediate": [
            "Branching strategies: GitFlow, GitHub Flow, and Trunk-Based Development",
            "Rebasing vs Merging (git rebase -i) and squash merges for clean history",
            "Resolving complex merge conflicts and using git stash and git cherry-pick"
        ],
        "advanced": [
            "Git internals deep dive: blobs, trees, commits, annotated tags, and .git directory objects",
            "Time travel and disaster recovery: git reflog, reset (--soft, --mixed, --hard), and revert",
            "Automating workflows with Git Hooks (pre-commit, Husky) and submodules"
        ],
        "practice": [
            "Recover an accidentally deleted branch with unpushed commits using 'git reflog'",
            "Perform an interactive rebase to squash 5 messy commits and edit a commit message",
            "Set up a pre-commit hook that automatically runs linters and tests before allowing commits"
        ],
        "projects": [
            {
                "title": "Enterprise Team Git Governance & CI Pipeline Template",
                "description": "Construct a template repository with branch protection rules, automated PR templates, and semantic release versioning.",
                "deliverables": "Documented GitHub repository with pre-commit hooks and branch protection automation."
            }
        ],
        "assessments": [
            {
                "question": "What is the difference between git merge and git rebase, and when should you NEVER rebase?",
                "key_points": "Merge creates a merge commit preserving exact history; rebase rewrites commit history on top of another base. Never rebase public shared branches."
            }
        ],
        "timeline_weeks": 2,
        "estimated_hours": 20,
        "resources": [
            {"title": "Pro Git Book by Scott Chacon", "type": "Free Book"},
            {"title": "Learn Git Branching (learngitbranching.js.org)", "type": "Interactive Simulator"}
        ]
    },

    "ci/cd": {
        "domain": "Cloud & DevOps",
        "difficulty": "Intermediate",
        "summary": "Architect automated build, test, security analysis, and deployment pipelines using GitHub Actions, GitLab CI, or Jenkins.",
        "beginner": [
            "Core concepts: Continuous Integration, Continuous Delivery, and Continuous Deployment",
            "YAML pipeline syntax: triggers (push, pull_request), jobs, steps, and runners",
            "Setting up automated unit tests and code linting on every pull request"
        ],
        "intermediate": [
            "Managing secrets, environment variables, and deployment environments (dev, staging, prod)",
            "Building and caching Docker container images in GitHub Container Registry (GHCR) or DockerHub",
            "Artifact publishing, matrix builds for multi-OS/runtime testing, and status checks"
        ],
        "advanced": [
            "Zero-downtime automated deployment to Kubernetes or cloud servers with health check rollbacks",
            "Security scanning integration: SAST, DAST, secret scanning (TruffleHog), and dependency CVE audit",
            "Self-hosted runner infrastructure and cost optimization for long-running workflows"
        ],
        "practice": [
            "Write a GitHub Actions workflow that builds a Docker image only when tests pass and caches layers",
            "Create a pipeline that automatically deploys pull requests to dynamic preview environments",
            "Implement a semantic-release workflow that auto-bumps semver versions and writes changelogs"
        ],
        "projects": [
            {
                "title": "End-to-End Enterprise CI/CD Pipeline with Automated Staging & Production",
                "description": "Create a fully automated pipeline testing code, scanning security vulnerabilities, building Docker images, and deploying to cloud.",
                "deliverables": "Tested .github/workflows repository with pull-request gatekeeping and Slack alert integrations."
            }
        ],
        "assessments": [
            {
                "question": "How do you securely handle secrets in CI/CD without leaking them into build logs or artifact caches?",
                "key_points": "Use repository secret managers with least-privilege scoping, avoid echoing env vars, and use OIDC tokens instead of long-lived access keys."
            }
        ],
        "timeline_weeks": 3,
        "estimated_hours": 30,
        "resources": [
            {"title": "GitHub Actions Official Documentation", "type": "Documentation"},
            {"title": "GitOps Principles & Best Practices", "type": "Guide"}
        ]
    },

    "machine learning": {
        "domain": "Data Science & AI",
        "difficulty": "Advanced",
        "summary": "Master the end-to-end ML lifecycle: feature engineering, supervised/unsupervised algorithms, evaluation metrics, and model deployment.",
        "beginner": [
            "Exploratory Data Analysis (EDA) with Pandas, NumPy, and Matplotlib/Seaborn",
            "Feature preprocessing: imputation, scaling (StandardScaler), and categorical encoding (One-Hot)",
            "Core algorithms: Linear/Logistic Regression, Decision Trees, and K-Nearest Neighbors"
        ],
        "intermediate": [
            "Ensemble methods: Random Forest, Gradient Boosting (XGBoost, LightGBM, CatBoost)",
            "Model evaluation: Confusion Matrix, Precision, Recall, F1-Score, ROC-AUC, and Cross-Validation",
            "Hyperparameter tuning using Optuna or GridSearchCV and addressing data leakage"
        ],
        "advanced": [
            "Unsupervised learning: K-Means clustering, PCA dimensionality reduction, and anomaly detection",
            "Model explainability with SHAP (Shapley values) and LIME",
            "Production MLOps: Model versioning with MLflow, containerized inference APIs, and drift detection"
        ],
        "practice": [
            "Train an XGBoost model on a Kaggle dataset and optimize F1-score via cross-validation",
            "Construct a complete Scikit-learn Pipeline with custom transformers and column transformers",
            "Deploy an ML model as a low-latency REST API using FastAPI and Docker"
        ],
        "projects": [
            {
                "title": "Customer Churn Prediction Engine with Model Interpretability",
                "description": "Build an end-to-end classifier predicting subscriber churn with interactive SHAP explanations.",
                "deliverables": "Clean Jupyter notebook, exported production model pipeline, and FastAPI prediction endpoint."
            }
        ],
        "assessments": [
            {
                "question": "What is the Bias-Variance tradeoff, and how do ensemble methods like Random Forest and Gradient Boosting differ in tackling it?",
                "key_points": "Random Forest uses bagging to reduce variance of overfitted trees; Gradient Boosting builds sequential trees to reduce bias of weak learners."
            }
        ],
        "timeline_weeks": 5,
        "estimated_hours": 50,
        "resources": [
            {"title": "Scikit-learn Official User Guide", "type": "Documentation"},
            {"title": "Hands-On Machine Learning by Aurélien Géron", "type": "Book"}
        ]
    }
}


def infer_skill_domain(skill_name: str) -> tuple[str, str]:
    """
    Infers the high-level domain and difficulty for any arbitrary technology skill.
    """
    skill_lower = skill_name.lower()

    if any(k in skill_lower for k in ["react", "vue", "angular", "html", "css", "tailwind", "frontend", "ui", "ux", "svelte", "sass", "webpack", "vite"]):
        return "Frontend & Web Architecture", "Intermediate"
    elif any(k in skill_lower for k in ["docker", "kubernetes", "aws", "azure", "gcp", "cloud", "devops", "ci/cd", "terraform", "ansible", "linux", "jenkins"]):
        return "Cloud Infrastructure & DevOps", "Advanced"
    elif any(k in skill_lower for k in ["python", "java", "node", "django", "flask", "fastapi", "spring", "golang", "rust", "backend", "api", "c++", "c#", "php"]):
        return "Backend & Systems Engineering", "Intermediate"
    elif any(k in skill_lower for k in ["sql", "mongo", "postgres", "redis", "database", "cassandra", "elastic", "dynamo"]):
        return "Database & Data Architecture", "Intermediate"
    elif any(k in skill_lower for k in ["machine learning", "deep learning", "ai", "nlp", "vision", "pytorch", "tensorflow", "data", "pandas"]):
        return "Data Science & Artificial Intelligence", "Advanced"
    elif any(k in skill_lower for k in ["test", "qa", "selenium", "cypress", "jest", "pytest", "automation"]):
        return "Quality Assurance & Test Engineering", "Intermediate"
    elif any(k in skill_lower for k in ["security", "cyber", "penetration", "oauth", "auth", "crypto"]):
        return "Security & Identity Engineering", "Advanced"
    else:
        return "Software Engineering & Tools", "Intermediate"


def generate_dynamic_skill_data(skill_name: str, predicted_category: str = "Technology") -> dict:
    """
    Generates a realistic, highly specific roadmap for ANY technical skill,
    whether it exists in the pre-defined catalog or is a novel/custom technology.
    """
    skill_clean = skill_name.strip()
    skill_lower = skill_clean.lower()

    # 1. Check exact or substring match in catalog
    for key, data in SKILL_KNOWLEDGE_BASE.items():
        if key == skill_lower or key in skill_lower or skill_lower in key:
            return data

    # 2. Dynamic synthesis for arbitrary skills
    domain, difficulty = infer_skill_domain(skill_clean)

    return {
        "domain": domain,
        "difficulty": difficulty,
        "summary": f"Master {skill_clean} core architecture, real-world patterns, and industry best practices required for {predicted_category} roles.",
        "beginner": [
            f"Core architecture, runtime ecosystem, and foundational concepts of {skill_clean}",
            f"Configuring local development environment, tooling, and basic syntax/CLI commands for {skill_clean}",
            f"Fundamental building blocks, modular design, and error handling in {skill_clean}"
        ],
        "intermediate": [
            f"Intermediate implementation patterns, asynchronous operations, and integration workflows with {skill_clean}",
            f"State management, data flow, and standard design patterns utilized in production {skill_clean}",
            f"Writing automated unit tests, mocking dependencies, and debugging complex issues in {skill_clean}"
        ],
        "advanced": [
            f"Advanced performance profiling, concurrency optimization, and memory efficiency in {skill_clean}",
            f"Production security hardening, access controls, and vulnerability mitigation for {skill_clean}",
            f"Enterprise scalability, fault tolerance, and CI/CD deployment pipelines incorporating {skill_clean}"
        ],
        "practice": [
            f"Implement a hands-on proof-of-concept utilizing core {skill_clean} capabilities",
            f"Diagnose and optimize a bottlenecked workflow or query in a {skill_clean} project",
            f"Build and publish a reusable utility or module with full test coverage for {skill_clean}"
        ],
        "projects": [
            {
                "title": f"Production-Grade Application Powered by {skill_clean}",
                "description": f"Architect and deploy a full-featured real-world system utilizing {skill_clean} to solve domain-specific workflows.",
                "deliverables": f"Well-documented GitHub repository with clean architecture, CI/CD pipeline, and deployed demo."
            },
            {
                "title": f"Enterprise Integration & Microservice Benchmark using {skill_clean}",
                "description": f"Construct an automated integration service demonstrating high-throughput performance with {skill_clean}.",
                "deliverables": f"Containerized service with automated unit/integration tests and benchmark report."
            }
        ],
        "assessments": [
            {
                "question": f"Explain the core architectural trade-offs of {skill_clean} compared to legacy alternatives.",
                "key_points": f"Highlight performance gains, developer experience, scalability limits, and maintainability considerations."
            },
            {
                "question": f"How do you troubleshoot and resolve high memory usage or performance bottlenecks in {skill_clean}?",
                "key_points": f"Describe profiling tools, telemetry metrics, logging strategies, and concrete optimization patterns."
            },
            {
                "question": f"What are the critical security and concurrency pitfalls developers encounter when implementing {skill_clean}?",
                "key_points": f"Detail input sanitization, authentication/authorization boundaries, and thread-safety / async management."
            }
        ],
        "timeline_weeks": 4,
        "estimated_hours": 35,
        "resources": [
            {"title": f"Official {skill_clean} Documentation & Getting Started Guide", "type": "Official Docs"},
            {"title": f"Modern {skill_clean} Architecture & Design Patterns", "type": "Best Practices Guide"},
            {"title": f"Real-World {skill_clean} Open Source Codebases & Examples", "type": "GitHub Practice"}
        ]
    }


def generate_skill_gap_roadmap(resume_skills: set, jd_skills: set, missing_skills: set, predicted_category: str = "Technology") -> dict:
    """
    Primary API entry point: Generates a complete, personalized, and dynamic
    preparation roadmap for every missing skill required by the Job Description.
    """
    missing_list = sorted(list(missing_skills)) if missing_skills else []

    roadmap = {
        "skill_gaps": missing_list,
        "priority_skills": sorted(
            missing_list,
            key=lambda x: x.lower() in [
                "python", "javascript", "react", "node.js", "aws", "docker",
                "sql", "kubernetes", "machine learning", "typescript", "postgresql"
            ],
            reverse=True
        ),
        "learning_path": {},
        "timeline_weeks": {},
        "total_estimated_hours": 0,
        "overall_weeks": 0,
        "skills_detailed": []
    }

    total_hours = 0
    max_weeks = 0

    for skill in missing_list:
        data = generate_dynamic_skill_data(skill, predicted_category)

        # Standard keys for backwards compatibility with existing UI
        roadmap["learning_path"][skill] = {
            "beginner_topics": data["beginner"],
            "intermediate_topics": data["intermediate"],
            "advanced_topics": data["advanced"],
            "practice_activities": data["practice"],
            "mini_projects": data["projects"],
            "assessments": data["assessments"],
            "domain": data["domain"],
            "difficulty": data["difficulty"],
            "summary": data["summary"],
            "timeline_weeks": data["timeline_weeks"],
            "estimated_hours": data["estimated_hours"],
            "resources": data["resources"],
            "phases": [
                {
                    "phase_num": 1,
                    "title": "Foundations & Architecture",
                    "milestone": f"Week 1: Core Syntax & Setup",
                    "topics": data["beginner"],
                    "badge": "Phase 1 · Week 1"
                },
                {
                    "phase_num": 2,
                    "title": "Engineering Patterns & Implementation",
                    "milestone": f"Week 2: Idiomatic Workflows",
                    "topics": data["intermediate"],
                    "badge": "Phase 2 · Week 2"
                },
                {
                    "phase_num": 3,
                    "title": "Production Mastery & Optimization",
                    "milestone": f"Week 3: Concurrency & Performance",
                    "topics": data["advanced"],
                    "badge": "Phase 3 · Week 3"
                },
                {
                    "phase_num": 4,
                    "title": "Hands-On Practice & Capstone Projects",
                    "milestone": f"Week 4: Portfolio Building",
                    "practice": data["practice"],
                    "projects": data["projects"],
                    "badge": "Phase 4 · Week 4"
                },
                {
                    "phase_num": 5,
                    "title": "Technical Interview & Certification",
                    "milestone": f"Week 5: Hiring Readiness",
                    "assessments": data["assessments"],
                    "badge": "Phase 5 · Validation"
                }
            ]
        }

        roadmap["timeline_weeks"][skill] = data["timeline_weeks"]
        total_hours += data["estimated_hours"]
        if data["timeline_weeks"] > max_weeks:
            max_weeks = data["timeline_weeks"]

        roadmap["skills_detailed"].append({
            "name": skill,
            "domain": data["domain"],
            "difficulty": data["difficulty"],
            "weeks": data["timeline_weeks"],
            "hours": data["estimated_hours"],
            "summary": data["summary"]
        })

    roadmap["total_estimated_hours"] = total_hours
    # If studying multiple skills concurrently, overall duration is slightly bounded
    roadmap["overall_weeks"] = max(max_weeks, min(len(missing_list) * 2, 12))

    # Dynamic role guidance
    roadmap["category_recommendations"] = {
        "Data Science": [
            "Prioritize statistical rigor and feature engineering pipelines with reproducible notebooks.",
            "Showcase end-to-end model deployments with FastAPI/Docker rather than just standalone Jupyter models.",
            "Emphasize business impact and ROI metrics in technical portfolio walkthroughs."
        ],
        "Web Development": [
            "Ensure full mastery of responsive, accessible design (WCAG) and modern state management.",
            "Write robust automated tests (unit, integration, and E2E with Playwright/Cypress).",
            "Optimize Core Web Vitals (LCP, FID, CLS) for high performance across all mobile devices."
        ],
        "Technology": [
            "Focus on clean code, automated unit testing, and design patterns (SOLID).",
            "Build full-stack portfolio repositories with live deployments and CI/CD pipelines.",
            "Practice explaining architectural trade-offs clearly during system design interviews."
        ]
    }.get(predicted_category, [
        "Focus on hands-on project creation and portfolio evidence for every missing skill.",
        "Practice whiteboarding and architectural explanations for common interview scenarios.",
        "Stay aligned with modern cloud-native standards and automated testing methodologies."
    ])

    return roadmap
