# REACH Frontend

A modern emergency alert dashboard built with **React**, **TypeScript**, **Vite**, and **Tailwind CSS**.

## ✨ Features

- **Interactive Map**: Powered by Mapbox GL JS with navigation controls, markers, and popups
- **Date Range Filtering**: Filter alerts by date range with preset options (Last 7 days, Last 30 days)
- **Detail Cards**: Sliding detail panel that shows comprehensive information about alerts
- **Responsive Design**: Built with Tailwind CSS v4 for mobile and desktop compatibility
- **React Components**: Modern React functional components with hooks and TypeScript
- **Real-time Updates**: Refresh alerts and update map markers dynamically

## 🚀 Setup Instructions

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Mapbox

1. Sign up for a free account at [Mapbox](https://www.mapbox.com/)
2. Create a new access token in your Mapbox dashboard
3. Replace the placeholder token in `src/App.tsx`:

```typescript
// Find this line in src/App.tsx
const MAPBOX_TOKEN =
  "pk.eyJ1IjoieW91ci11c2VybmFtZSIsImEiOiJjbDI0eXNwbGQwMDEwM2JtcXJ5NGQ4ZGVtIn0.example";

// Replace with your actual token
const MAPBOX_TOKEN = "your_actual_mapbox_token_here";
```

### 3. Run the Development Server

```bash
npm run dev
```

The application will be available at `http://localhost:5173`

## 📁 Project Structure

```
src/
├── components/
│   ├── MapComponent.tsx        # Mapbox React component with forwardRef
│   ├── DateRangeSelector.tsx   # Date filtering React component
│   └── DetailCard.tsx          # Alert detail sidebar React component
├── App.tsx                     # Main React application component
├── main.tsx                    # React app entry point
└── style.css                   # Global styles and Tailwind imports
```

## 🏗️ Database Schema Integration

This frontend is designed to work with the database schema defined in `../Prototype/schema.dbml`, supporting:

- **Documents**: Source tracking (NDMA, NEOC, etc.)
- **Places**: Geographic hierarchy and polygons
- **Alerts**: CAP-compliant alert system with categories, urgency, and severity
- **Alert Areas**: Location-specific alert details

## 📱 Usage

1. **Map Interaction**: Click anywhere on the map to create a sample alert at that location
2. **Alert List**: Click on any alert in the sidebar to view details and zoom to its location
3. **Date Filtering**: Use the date range selector to filter alerts by date
4. **Detail Panel**: View comprehensive alert information with severity indicators and instructions
5. **Refresh**: Use the refresh button to reload alerts (in production, this would fetch from API)

## 🎯 Sample Data

The application includes sample alerts for demonstration:

- **Flood Warning** in Kathmandu Valley (Severe, Expected)
- **Landslide Risk** in Pokhara Region (Moderate, Expected)
- **Air Quality Alert** in Biratnagar (Minor, Immediate)

## 🔮 Next Steps

1. **API Integration**: Connect to a backend API that serves data from the database schema
2. **Real-time Updates**: Implement WebSocket connections for live alert updates
3. **User Authentication**: Add login/logout functionality with React context
4. **Advanced Filtering**: Add filters by category, severity, urgency, and source
5. **Offline Support**: Implement service workers for offline functionality
6. **Testing**: Add unit tests with Jest and React Testing Library
7. **State Management**: Implement Redux or Zustand for complex state management

## 🛠️ Technologies Used

- **React 18**: Modern React with functional components and hooks
- **TypeScript**: Type-safe JavaScript development
- **Vite**: Lightning-fast build tool and dev server
- **Tailwind CSS v4**: Utility-first CSS framework
- **Mapbox GL JS**: Interactive maps with React integration
- **date-fns**: Modern date manipulation utilities

## 🎨 Component Architecture

### MapComponent

- **forwardRef** for imperative map operations
- TypeScript interfaces for props and ref methods
- Automatic marker management and cleanup
- Click event handling with coordinates

### DateRangeSelector

- React state for date management
- Preset date range buttons
- Form validation and date swapping logic
- Callback props for parent component communication

### DetailCard

- Conditional rendering based on data availability
- Severity and urgency color coding
- Smooth slide-in animations with Tailwind CSS
- Action buttons with callback handling

### App (Main Component)

- React hooks for state management (useState, useRef)
- Component composition and data flow
- Event handling and business logic
- Sample data integration

This React-powered dashboard provides a solid foundation for building a production-ready emergency alert system with modern web technologies! 🎉
