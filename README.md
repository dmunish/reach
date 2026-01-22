<p align="center">
  <img src="https://github.com/dmunish/reach/blob/main/Assets/REACH-Banner.png?raw=true" height=400 width="auto" alt="REACH Banner" />
</p>

# REACH

<p align="center">
  <b>Real-time Emergency Alert Collection Hub</b>
</p>
<p align="center">
  An AI-powered bridge between official disaster forecasts and community preparedness.
</p>

<div align="center">

  <img src="https://img.shields.io/badge/Status-In%20Development-orange?style=for-the-badge" alt="Status" />
  <img src="https://img.shields.io/badge/Stack-React%20%7C%20Python%20%7C%20Supabase-blue?style=for-the-badge" alt="Stack" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License" />

</div>

<p align="center">
  <img src="https://via.placeholder.com/800x450.png?text=App+Dashboard+Demo+(Map+Visualization)" alt="REACH Dashboard Demo" width="100%" style="border-radius: 10px; box-shadow: 0 4px 8px 0 rgba(0, 0, 0, 0.2), 0 6px 20px 0 rgba(0, 0, 0, 0.19);" />
</p>


## <img src="https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/telescope.svg" width="24" height="24" style="vertical-align: middle; filter: invert(1);"> The Problem
Pakistan faces a critical disconnect in its disaster management infrastructure. While agencies like NDMA and PMD generate vital data, the "last mile" of communication is broken.

<table width="100%">
  <tr>
    <td width="33%" valign="top">
      <h3 align="center"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00b887" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-puzzle-icon lucide-puzzle"><path d="M15.39 4.39a1 1 0 0 0 1.68-.474 2.5 2.5 0 1 1 3.014 3.015 1 1 0 0 0-.474 1.68l1.683 1.682a2.414 2.414 0 0 1 0 3.414L19.61 15.39a1 1 0 0 1-1.68-.474 2.5 2.5 0 1 0-3.014 3.015 1 1 0 0 1 .474 1.68l-1.683 1.682a2.414 2.414 0 0 1-3.414 0L8.61 19.61a1 1 0 0 0-1.68.474 2.5 2.5 0 1 1-3.014-3.015 1 1 0 0 0 .474-1.68l-1.683-1.682a2.414 2.414 0 0 1 0-3.414L4.39 8.61a1 1 0 0 1 1.68.474 2.5 2.5 0 1 0 3.014-3.015 1 1 0 0 1-.474-1.68l1.683-1.682a2.414 2.414 0 0 1 3.414 0z"/></svg> Fragmentation</h3>
      <p align="center">Critical alerts are scattered across isolated agencies, or locked inside static PDF bulletins.</p>
    </td>
    <td width="33%" valign="top">
      <h3 align="center"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00b887" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-snail-icon lucide-snail"><path d="M2 13a6 6 0 1 0 12 0 4 4 0 1 0-8 0 2 2 0 0 0 4 0"/><circle cx="10" cy="13" r="8"/><path d="M2 21h12c4.4 0 8-3.6 8-8V7a2 2 0 1 0-4 0v6"/><path d="M18 3 19.1 5.2"/><path d="M22 3 20.9 5.2"/></svg> Latency & Jargon</h3>
      <p align="center">Reports are often verbose, technical, and require manual parsing, leading to dangerous delays in dissemination.</p>
    </td>
    <td width="33%" valign="top">
      <h3 align="center"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00b887" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-locate-fixed-icon lucide-locate-fixed"><line x1="2" x2="5" y1="12" y2="12"/><line x1="19" x2="22" y1="12" y2="12"/><line x1="12" x2="12" y1="2" y2="5"/><line x1="12" x2="12" y1="19" y2="22"/><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="3"/></svg> Zero Targeting</h3>
      <p align="center">Warnings are broadcast at the national level, causing alert fatigue. There is no proper system to notify <i>only</i> the specific region at risk. The few systems that do exist for this targeting are faulty.</p>
    </td>
  </tr>
</table>


## <img src="https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/cpu.svg" width="24" height="24" style="vertical-align: middle; filter: invert(1);"> The Solution
REACH is an automated pipeline that ingests raw government data and transforms it into precision-targeted, actionable alerts. We treat disaster alerts as **spatial data problems**, not just text problems.

### How it works
<p align="center">
  <img src="https://via.placeholder.com/700x300.png?text=Scraper+%E2%86%92+Message+Queue+%E2%86%92+Gemini+Flash+%E2%86%92+Geocoder+%E2%86%92+Supabase" alt="Architecture Diagram" />
</p>

1.  **Ingestion:** Microservice scrapers monitor endpoints (NDMA, NEOC, PMD) every 10 minutes.
2.  **Normalization:** AI processes unstructured text and PDFs in under 30 seconds to extract severity, timeline, description, etc. and convert to a CAP-compliant schema.
3.  **Geocoding:** A custom engine resolves location names to polygons. It handles complex directional variants (e.g., "North Khyber Pakhtunkhwa") using grid intersection logic over administrative boundaries.
4.  **Distribution:** Normalized data is stored in our database and served via web app for visualization and filtering.


## <img src="https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/layers.svg" width="24" height="24" style="vertical-align: middle; filter: invert(1);"> Tech Stack
Our architecture is built for speed, resilience, and geospatial accuracy.

| **Component**            | **Technology**                                                                                                         | **Description**                                                                     |
| :----------------------- | :--------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------- |
| **Frontend**             | <img src="https://skillicons.dev/icons?i=react,ts,tailwind" valign="middle" />                                         | React, TypeScript, and Mapbox for web app.                                          |
| **Services**             | <img src="https://skillicons.dev/icons?i=python,fastapi" valign="middle" />                                            | Python microservices handling business logic and scraping.                          |
| **AI Engine**            | <img src="https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/google-gemini.svg" width="40" valign="middle" /> | Gemini-3-Flash for high-speed inference for document parsing and entity extraction. |
| **Backend and Database** | <img src="https://skillicons.dev/icons?i=supabase,postgres" valign="middle" />                                         | **Supabase** for storing alerts, geometries, cron jobs and message queues           |


## <img src="https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/wallpaper.svg" width="24" height="24" style="vertical-align: middle; filter: invert(1);"> Visuals

|                               **Alert Polygon Visualization**                               |                                  **Search & Filtering**                                  |
| :-----------------------------------------------------------------------------------------: | :--------------------------------------------------------------------------------------: |
| <img src="https://via.placeholder.com/400x250.png?text=Geospatial+Polygons" width="100%" /> | <img src="https://via.placeholder.com/400x250.png?text=Filter+Interface" width="100%" /> |



## <img src="https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/map.svg" width="24" height="24" style="vertical-align: middle; filter: invert(1);"> Roadmap
- [x] **Scrapers:** Automated bots hitting NDMA, NEOC, and PMD public sources on a 10-minute cron
- [x] **AI Pipeline:** Document processing pipeline achieving <30s latency per report using Gemini 3 Flash
- [x] **Spatial Engine:** Heuristic geocoder capable of parsing admin regions and directional descriptors into polygons
- [x] **Web Dashboard:** A responsive React application for searching alerts, filtering by severity/date, and visualizing risk zones on an interactive map
- [ ] **Mobile Apps:** Apps for Android and iOS to get information to all users conveniently
- [ ] **Alerts:** Notifications for iOS/Android and web apps based on user GPS location
- [ ] **Advanced Geocoding:** Improving the heuristic engine to resolve roadways, hydrology (rivers/dams), and bridges
- [ ] **Deduplication:** Logic to merge overlapping reports from different agencies into a single "Source of Truth" event
- [ ] **Data Expansion:** Integrating social media firehose (validated) and international weather APIs.
- [ ] **Performance:** Optimizing PostGIS queries for faster polygon rendering
- [ ] **UX Polish:** Refining the dashboard based on early user feedback


## <img src="https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/heart-handshake.svg" width="24" height="24" style="vertical-align: middle; filter: invert(1);"> Acknowledgements
- NDMA, NEOC, and PMD for their tireless work in disaster monitoring
- The open-source community for incredible tools and libraries
- Communities affected by the 2025 floods - this is for you

<p align="center">
  <sub>Built with <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="#00b887" stroke="#00b887" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-heart-icon lucide-heart"><path d="M2 9.5a5.5 5.5 0 0 1 9.591-3.676.56.56 0 0 0 .818 0A5.49 5.49 0 0 1 22 9.5c0 2.29-1.5 4-3 5.5l-5.492 5.313a2 2 0 0 1-3 .019L5 15c-1.5-1.5-3-3.2-3-5.5"/></svg> for a safer Pakistan.</sub>
</p>