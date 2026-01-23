<p align="center">
  <img src="https://github.com/dmunish/reach/blob/main/Assets/REACH-Banner.png?raw=true" height=400 width="auto" alt="REACH Banner" />
</p>

# REACH

<p align="center">
  <b>Real-time Emergency Alert Collection Hub</b>
</p>
<p align="center">
  An AI-powered warning system to bridge official disaster forecasts and the community in Pakistan.
</p>

<div align="center">

  <img src="https://img.shields.io/badge/Status-In%20Development-orange?style=for-the-badge" alt="Status" />
  <img src="https://img.shields.io/badge/Stack-React%20%7C%20Python%20%7C%20Supabase-blue?style=for-the-badge" alt="Stack" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License" />

</div>

<br>

## <img src="Assets\telescope-green.svg" width="24" height="24" style="vertical-align: middle; filter: invert(1);"> The Problem
Pakistan faces a critical disconnect in its disaster management infrastructure. While agencies like NDMA and PMD generate vital data, the "last mile" of communication is broken.

<table width="100%">
  <tr>
    <td width="33%" valign="top">
      <h3 align="center"><img src="Assets\circle-pile-green.svg" width="20" height="20" style="vertical-align: middle;"> Fragmentation</h3>
      <p align="center">Critical alerts are scattered across isolated agencies, or locked inside static PDF bulletins.</p>
    </td>
    <td width="33%" valign="top">
      <h3 align="center"><img src="Assets\snail-green.svg" width="20" height="20" style="vertical-align: middle;"> Latency & Jargon</h3>
      <p align="center">Reports are often verbose, technical, and require manual parsing, leading to dangerous delays in dissemination.<br></p>
    </td>
    <td width="33%" valign="top">
      <h3 align="center"><img src="Assets\locate-fixed-green.svg" width="20" height="20" style="vertical-align: middle;"> Zero Targeting</h3>
      <p align="center">Warnings are broadcast at the national level, causing alert fatigue. Faulty systems to deliver geofenced alerts.<br><br></p>
    </td>
  </tr>
</table>

<br>

## <img src="Assets\cpu-green.svg" width="24" height="24" style="vertical-align: middle;"> The Solution
REACH is an automated pipeline that ingests raw government data and transforms it into precision-targeted, actionable alerts. We treat disaster alerts as **spatial data problems**, not just text problems.

### How it works
<p align="center">
  <img src="Assets\REACH-Architecture.png" width="auto" height="400" alt="Architecture Diagram" />
</p>

1.  **Ingestion:** Scrapers check bulletins (NDMA, NEOC, PMD) every 10 minutes for updates.
2.  **Normalization:** AI processes fetched documents in under 30 seconds to extract severity, timeline, description, etc. and convert it to a CAP (Common Alerting Protocol)-inspired schema.
3.  **Geocoding:** A custom service resolves location names to polygons. It handles complex directional variants (e.g., "North Khyber Pakhtunkhwa") using grid intersection logic over administrative boundaries.
4.  **Distribution:** Normalized data is stored in our database and served via web app for visualization and filtering.

<br>

## <img src="Assets\layers-green.svg" width="24" height="24" style="vertical-align: middle; filter: invert(1);"> Tech Stack
Our architecture is built for speed, resilience, and geospatial accuracy.

| **Component**            | **Technology**                                                                                                         | **Description**                                                                     |
| :----------------------- | :--------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------- |
| **Frontend**             | <img src="https://skillicons.dev/icons?i=react,ts,tailwind" valign="middle" />                                         | React, TypeScript, and Mapbox for web app.                                          |
| **Services**             | <img src="https://skillicons.dev/icons?i=python,fastapi" valign="middle" />                                            | Python microservices handling business logic and scraping.                          |
| **Backend and Database** | <img src="https://skillicons.dev/icons?i=supabase,postgres" valign="middle" />                                         | **Supabase** for storing alerts, geometries, cron jobs and message queues           |
| **AI Engine**            | <img src="https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/google-gemini.svg" width="40" valign="middle" /> | Gemini-3-Flash for high-speed inference for document parsing and entity extraction. |

<br>

## <img src="Assets\images-green.svg" width="24" height="24" style="vertical-align: middle; filter: invert(1);"> Visuals

|                               **Alert Polygon and Centroid Visualization**                               |                               **Searching Historical Alerts**                               |
| :-----------------------------------------------------------------------------------------: | :-----------------------------------------------------------------------------------------: |
| <img src="Assets/Screenshot-Polygon-Centroid.png" width="100%" /> |  <img src="Assets/Screenshot-Searching.png" width="100%" />   |
|                                  **Filtering By Location**                                  |                                       **Signup Page**                                       |
| <img src="Assets/Screenshot-Filtering-Location.png" width="100%" /> | <img src="Assets/Screenshot-Singup-Page.png" width="100%" /> |

<br>

## <img src="Assets\map-green.svg" width="24" height="24" style="vertical-align: middle; filter: invert(1);"> Roadmap
- [x] **Scrapers:** Automated bots hitting NDMA, NEOC, and PMD public sources on a 10-minute cron
- [x] **AI Pipeline:** Document processing pipeline achieving <30s latency per report using Gemini 3 Flash
- [x] **Spatial Engine:** Heuristic geocoder capable of parsing admin regions and directional descriptors into polygons
- [x] **Web Dashboard:** A responsive React application for searching alerts, filtering by severity/date, and visualizing risk zones on an interactive map
- [ ] **Deduplication:** Logic to merge overlapping reports from different agencies into a single "Source of Truth" event
- [ ] **UX Polish:** Refining the dashboard based on early user feedback
- [ ] **Alerts:** Notifications for user apps based on their GPS location
- [ ] **Performance:** Optimizing database and backend for better performance
- [ ] **Mobile Apps:** Apps for Android and iOS to get information to all users conveniently
- [ ] **Advanced Geocoding:** Improving the heuristic engine to resolve roadways, hydrology (rivers/dams), and bridges
- [ ] **Data Expansion:** Integrating social media firehose (validated) and international weather APIs

<br>

## <img src="Assets\heart-handshake-green.svg" width="24" height="24" style="vertical-align: middle; filter: invert(1);"> Acknowledgements
- NDMA, NEOC, and PMD for their tireless work in disaster monitoring
- The open-source community for incredible tools and libraries
- Render, Modal, Supabase and Netlify for allowing us to host our app's services for free
- Communities affected by the 2025 floods - this is for you

<br>

<p align="center">
  <sub>Built with <img src="Assets\heart-solid-green.svg" width="12" height="12" style="vertical-align: middle;"> for a safer Pakistan.</sub>
</p>