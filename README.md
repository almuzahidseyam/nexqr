# 🚀 NexQR - Ultimate QR Code Suite

An Enterprise-grade SaaS application and Chrome Extension for generating, securing, and tracking dynamic QR codes.

## 🔥 Features
- **Standard QR:** Fast, offline-ready QR generation.
- **Dynamic QR:** Trackable links that can be updated anytime.
- **Secure AES QR:** Zero-knowledge password-encrypted QR payloads via CryptoJS.
- **AI Artistic QR:** Generates beautiful QRs via Stable Diffusion & ControlNet (Replicate API).
- **Chrome Extension Sync:** Generate dynamic QRs directly from any tab.
- **Advanced Analytics:** Tracks IPs (GDPR compliant masked), Devices, and Browsers.

## 🛠️ Security & Architecture
- **Zero-Defect Architecture:** Hardened against SQLi, XSS, CSRF.
- **Anti-DoS Redirects:** Fallback try/except wrappers prevent DB lockouts during traffic spikes.
- **Strict CORS Policy:** API is locked down exclusively to the Chrome Extension origin.
- **Collision-Proof:** Custom short-code generation loops prevent ID collisions.

## 💻 Tech Stack
- **Backend:** Django (Python), SQLite
- **Frontend:** HTML5, Tailwind CSS, Vanilla JS
- **Extension:** Manifest V3, Web Fetch API

## 📝 License
MIT License. Copyright (c) 2026 Muhammad Al-Muzahid.
