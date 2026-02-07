import { useEffect, useRef, forwardRef, useImperativeHandle } from "react";
import mapboxgl from "mapbox-gl";
import customStyle from "./style.json";

export interface MapProps {
  accessToken: string;
  center?: [number, number];
  zoom?: number;
  theme?: string;
  showPolygons?: boolean;
  onMapClick?: (
    coordinates: [number, number],
    event: mapboxgl.MapMouseEvent
  ) => void;
  markers?: Array<{
    coordinates: [number, number];
    popupContent?: string;
    severity?: string;
    onClick?: () => void | Promise<void>;
    onHover?: () => void | Promise<void>;
  }>;
  className?: string;
}

export interface MapRef {
  flyTo: (coordinates: [number, number], zoomLevel?: number) => void;
  getMap: () => mapboxgl.Map | null;
  highlightPolygon: (geometries: any | any[]) => void;
  highlightGeoJSON: (geometry: any) => void;
  fitToPolygons: (geometries: any | any[], padding?: number) => void;
  fitToBbox: (bbox: { xmin: number; ymin: number; xmax: number; ymax: number }, padding?: number) => void;
  clearHighlight: () => void;
}

export const MapComponent = forwardRef<MapRef, MapProps>(
  (
    {
      accessToken,
      center = [69.3451, 30.3753], // Default to Pakistan center
      zoom = 3,
      theme = "dark-v11",
      showPolygons = true,
      onMapClick,
      markers = [],
      className = "w-full h-full",
    },
    ref
  ) => {
    const mapContainer = useRef<HTMLDivElement>(null);
    const map = useRef<mapboxgl.Map | null>(null);
    const markersRef = useRef<mapboxgl.Marker[]>([]);
    const markersDataRef = useRef<MapProps["markers"]>([]); // Store markers data for interaction
    const activeHighlightRef = useRef<any>(null); // Track currently highlighted geometry for persistence

    // Initialize map
    useEffect(() => {
      if (!mapContainer.current || map.current) return; // Don't reinitialize if map already exists

      // Set the access token
      mapboxgl.accessToken = accessToken;

      // Determine map style based on theme
      const mapStyle =
        theme === "dark-v11"
          ? "mapbox://styles/mapbox/dark-v11"
          : (customStyle as any);

      // Create the map
      map.current = new mapboxgl.Map({
        container: mapContainer.current,
        style: mapStyle,
        center: center,
        zoom: zoom,
        preserveDrawingBuffer: true, // Help prevent context loss
        antialias: false, // Reduce GPU load
      });

      // Handle WebGL context loss
      map.current.on("webglcontextlost", (e) => {
        console.warn("WebGL context lost");
        if (e.originalEvent) {
          e.originalEvent.preventDefault();
        }
      });

      // Handle WebGL context restore
      map.current.on("webglcontextrestored", () => {
        console.log("WebGL context restored");
        // Re-apply active highlight if one exists
        if (activeHighlightRef.current) {
          highlightGeoJSON(activeHighlightRef.current);
        }
      });

      // Add navigation controls
      map.current.addControl(new mapboxgl.NavigationControl(), "top-left");

      // Add full screen control
      map.current.addControl(new mapboxgl.FullscreenControl(), "top-left");

      // Add scale control
      map.current.addControl(
        new mapboxgl.ScaleControl({
          maxWidth: 100,
          unit: "metric",
        }),
        "bottom-left"
      );

      // Handle map clicks if callback provided
      if (onMapClick) {
        map.current.on("click", (e) => {
          const coordinates: [number, number] = [e.lngLat.lng, e.lngLat.lat];
          onMapClick(coordinates, e);
        });
      }

      // Cleanup function
      return () => {
        if (map.current) {
          // Remove all markers first
          markersRef.current.forEach(marker => {
            marker.remove();
          });
          markersRef.current = [];
          markersDataRef.current = [];
          
          // Remove the map - this automatically cleans up all event listeners
          map.current.remove();
          map.current = null;
        }
      };
    }, [accessToken]); // Only depend on accessToken to minimize re-initialization

    // Handle theme changes
    useEffect(() => {
      if (!map.current) return;

      const mapStyle =
        theme === "dark-v11"
          ? "mapbox://styles/mapbox/dark-v11"
          : (customStyle as any);

      map.current.setStyle(mapStyle);

      // Re-apply highlights after style change
      map.current.once("style.load", () => {
        if (activeHighlightRef.current) {
          highlightGeoJSON(activeHighlightRef.current);
        }
      });
    }, [theme]);

    // Update markers when markers prop changes
    useEffect(() => {
      if (!map.current) return;

      markersDataRef.current = markers;

      // Clear existing markers
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];

      // Severity color mapping
      const getSeverityColors = (severity?: string): { main: string; pulse: string } => {
        switch (severity?.toLowerCase()) {
          case 'extreme':
            return { main: 'rgba(180, 0, 255, 0.9)', pulse: 'rgba(180, 0, 255, 0.6)' }; // Vibrant Purple
          case 'severe':
            return { main: 'rgba(220, 20, 60, 0.9)', pulse: 'rgba(220, 20, 60, 0.6)' }; // Crimson
          case 'moderate':
            return { main: 'rgba(255, 140, 0, 0.9)', pulse: 'rgba(255, 140, 0, 0.6)' }; // Dark Orange
          case 'minor':
            return { main: 'rgba(255, 215, 0, 0.9)', pulse: 'rgba(255, 215, 0, 0.6)' }; // Gold
          case 'user':
            return { main: 'rgba(30, 144, 255, 0.9)', pulse: 'rgba(30, 144, 255, 0)' }; // User Pin (No pulse)
          case 'unknown':
          default:
            return { main: 'rgba(30, 144, 255, 0.9)', pulse: 'rgba(30, 144, 255, 0.6)' }; // Dodger Blue
        }
      };

      // Add new markers
      markers.forEach(({ coordinates, popupContent, severity, onClick, onHover }) => {
        const colors = getSeverityColors(severity);
        const isUserMarker = severity?.toLowerCase() === 'user';
        
        // Create custom marker element with glassmorphic design
        const el = document.createElement("div");
        el.className = "custom-marker";
        el.innerHTML = `
          <div style="position: relative; width: 28px; height: 28px;">
            ${!isUserMarker ? `<div style="position: absolute; width: 28px; height: 28px; background: ${colors.pulse}; border-radius: 50%; animation: pulse 2s ease-out infinite;"></div>` : ''}
            <div style="
              position: absolute; 
              width: 20px; 
              height: 20px; 
              top: 4px; 
              left: 4px; 
              background: ${colors.main};
              border: 2px solid rgba(255, 255, 255, 0.4);
              border-radius: 50%;
              box-shadow: 
                0 4px 12px ${isUserMarker ? 'rgba(30, 144, 255, 0.4)' : colors.pulse},
                inset 0 1px 2px rgba(255, 255, 255, 0.3),
                0 1px 3px rgba(0, 0, 0, 0.2);
            "></div>
          </div>
        `;
        el.style.cursor = "pointer";

        // Add pulse animation
        const style = document.createElement("style");
        style.textContent = `
          @keyframes pulse {
            0% { transform: scale(1); opacity: 0.5; }
            50% { transform: scale(1.5); opacity: 0.2; }
            100% { transform: scale(2); opacity: 0; }
          }
        `;
        if (!document.head.querySelector("style[data-marker-pulse]")) {
          style.setAttribute("data-marker-pulse", "true");
          document.head.appendChild(style);
        }

        const marker = new mapboxgl.Marker({ element: el, anchor: "center" })
          .setLngLat(coordinates)
          .addTo(map.current!);

        if (popupContent) {
          const popup = new mapboxgl.Popup({ offset: 25 }).setHTML(
            popupContent
          );
          marker.setPopup(popup);
        }

        if (onClick) {
          el.addEventListener("click", (e) => {
            e.stopPropagation(); // Prevent map click event
            onClick();
          });
        }

        if (onHover) {
          el.addEventListener("mouseenter", () => {
            onHover();
          });
        }

        markersRef.current.push(marker);
      });
    }, [markers]);

    // Fly to location
    const flyTo = (coordinates: [number, number], zoomLevel?: number) => {
      if (!map.current) return;

      map.current.flyTo({
        center: coordinates,
        zoom: zoomLevel || map.current.getZoom(),
        essential: true,
      });
    };

    // Function to convert PostGIS geometry to GeoJSON
    const convertToGeoJSON = (geometry: any): any => {
      if (!geometry) return null;

      try {
        if (typeof geometry === "string") {
          // Parse WKT format
          const polygonMatch = geometry.match(
            /POLYGON\s*\(\s*\(\s*([\d.-\s,]+)\s*\)\s*\)/i
          );
          if (polygonMatch) {
            const coordString = polygonMatch[1];
            const coordinates: number[][] = [];

            const coordPairs = coordString.split(",");
            coordPairs.forEach((pair) => {
              const coords = pair.trim().split(/\s+/);
              if (coords.length >= 2) {
                const lng = parseFloat(coords[0]);
                const lat = parseFloat(coords[1]);
                if (!isNaN(lng) && !isNaN(lat)) {
                  coordinates.push([lng, lat]);
                }
              }
            });

            return {
              type: "Feature",
              geometry: {
                type: "Polygon",
                coordinates: [coordinates],
              },
            };
          }
        } else if (geometry && typeof geometry === "object") {
          if (geometry.type === "Polygon") {
            return {
              type: "Feature",
              geometry: geometry,
            };
          }
        }
      } catch (error) {
        console.warn("Failed to convert geometry to GeoJSON:", error);
      }

      return null;
    };

    const highlightPolygon = (geometries: any | any[]) => {
      if (!map.current) {
        console.warn("Map not available for highlighting");
        return;
      }

      // Don't show polygons if setting is disabled
      if (!showPolygons) {
        console.log("Polygon display is disabled in settings");
        return;
      }

      // Wait for map to be fully loaded
      if (!map.current.isStyleLoaded()) {
        console.log("Map style not loaded yet, waiting...");
        map.current.once("styledata", () => {
          highlightPolygon(geometries);
        });
        return;
      }

      // Ensure geometries is an array
      const geometryArray = Array.isArray(geometries) ? geometries : [geometries];
      
      console.log("Highlighting polygons with geometries:", geometryArray);

      // Convert all geometries to GeoJSON features
      const features = geometryArray
        .map(convertToGeoJSON)
        .filter((feature) => feature !== null);

      if (features.length === 0) {
        console.warn("No valid geometries to highlight");
        return;
      }

      console.log(`Converted ${features.length} geometry(ies) to GeoJSON`);

      try {
        // Remove existing highlight if any
        clearHighlight();

        // Check if map is still valid before adding layers
        if (!map.current.getStyle()) {
          console.warn("Map style not available, skipping polygon highlight");
          return;
        }

        // Create a FeatureCollection from all features
        const featureCollection = {
          type: "FeatureCollection",
          features: features,
        };

        // Add the polygons as a source
        map.current.addSource("highlighted-polygon", {
          type: "geojson",
          data: featureCollection as any,
        });

        // Add fill layer
        map.current.addLayer({
          id: "highlighted-polygon-fill",
          type: "fill",
          source: "highlighted-polygon",
          paint: {
            "fill-color": [
              "interpolate",
              ["linear"],
              ["zoom"],
              0, "#003020",   // Darker at global view to compensate for ambient light
              6, "#004530",   // Transition
              10, "#006240"   // Intended color at street level
            ],
            "fill-opacity": 0.25,
            "fill-emissive-strength": 1, // Ensure visibility in Standard style night mode
          },
        });

        // Add outline layer
        map.current.addLayer({
          id: "highlighted-polygon-outline",
          type: "line",
          source: "highlighted-polygon",
          paint: {
            "line-color": "#2fa96c", // Mint green - softer outline
            "line-width": 2,
            "line-emissive-strength": 1, // Ensure visibility in Standard style night mode
          },
        });

        console.log(`Successfully highlighted ${features.length} polygon(s)`);
      } catch (error) {
        console.warn(
          "Failed to add polygon highlight (context may be lost):",
          error
        );
        // Try to recover by waiting and retrying once
        setTimeout(() => {
          try {
            if (map.current && map.current.getStyle()) {
              highlightPolygon(geometries);
            }
          } catch (retryError) {
            console.warn("Retry failed, polygon highlighting unavailable");
          }
        }, 100);
      }
    };

    // Function to extract all coordinates from a geometry for bounds calculation
    const extractCoordinatesFromGeometry = (geometry: any): number[][] => {
      const coords: number[][] = [];
      
      if (!geometry) return coords;

      try {
        if (typeof geometry === "string") {
          const polygonMatch = geometry.match(
            /POLYGON\s*\(\s*\(\s*([\d.-\s,]+)\s*\)\s*\)/i
          );
          if (polygonMatch) {
            const coordString = polygonMatch[1];
            const coordPairs = coordString.split(",");
            coordPairs.forEach((pair) => {
              const parts = pair.trim().split(/\s+/);
              if (parts.length >= 2) {
                const lng = parseFloat(parts[0]);
                const lat = parseFloat(parts[1]);
                if (!isNaN(lng) && !isNaN(lat)) {
                  coords.push([lng, lat]);
                }
              }
            });
          }
        } else if (geometry && typeof geometry === "object") {
          if (geometry.type === "Polygon" && geometry.coordinates?.[0]) {
            geometry.coordinates[0].forEach((coord: number[]) => {
              if (coord.length >= 2) {
                coords.push([coord[0], coord[1]]);
              }
            });
          } else if (geometry.type === "Point" && geometry.coordinates) {
            coords.push([geometry.coordinates[0], geometry.coordinates[1]]);
          }
        }
      } catch (error) {
        console.warn("Failed to extract coordinates:", error);
      }

      return coords;
    };

    // Function to fit map bounds to show all polygons
    const fitToPolygons = (geometries: any | any[], padding: number = 50) => {
      if (!map.current) {
        console.warn("Map not available for fitting bounds");
        return;
      }

      const geometryArray = Array.isArray(geometries) ? geometries : [geometries];
      
      // Collect all coordinates from all geometries
      let allCoords: number[][] = [];
      geometryArray.forEach((geom) => {
        const coords = extractCoordinatesFromGeometry(geom);
        allCoords = allCoords.concat(coords);
      });

      if (allCoords.length === 0) {
        console.warn("No valid coordinates found for fitting bounds");
        return;
      }

      // Calculate bounds
      let minLng = Infinity;
      let maxLng = -Infinity;
      let minLat = Infinity;
      let maxLat = -Infinity;

      allCoords.forEach(([lng, lat]) => {
        minLng = Math.min(minLng, lng);
        maxLng = Math.max(maxLng, lng);
        minLat = Math.min(minLat, lat);
        maxLat = Math.max(maxLat, lat);
      });

      // Create bounds and fit map
      const bounds = new mapboxgl.LngLatBounds(
        [minLng, minLat],
        [maxLng, maxLat]
      );

      map.current.fitBounds(bounds, {
        padding: padding,
        maxZoom: 12, // Don't zoom in too much for small polygons
        duration: 1000, // Smooth animation
      });

      console.log(`Fitted map to bounds: [${minLng}, ${minLat}] - [${maxLng}, ${maxLat}]`);
    };

    const clearHighlight = () => {
      if (!map.current) return;

      activeHighlightRef.current = null;

      try {
        // Remove layers if they exist
        if (map.current.getLayer("highlighted-polygon-fill")) {
          map.current.removeLayer("highlighted-polygon-fill");
        }
        if (map.current.getLayer("highlighted-polygon-outline")) {
          map.current.removeLayer("highlighted-polygon-outline");
        }
        // Remove source if it exists
        if (map.current.getSource("highlighted-polygon")) {
          map.current.removeSource("highlighted-polygon");
        }
      } catch (error) {
        console.warn(
          "Failed to clear polygon highlight (this is normal after context loss):",
          error
        );
      }
    };

    // Function to highlight a GeoJSON geometry directly (from RPC response)
    const highlightGeoJSON = (geometry: any) => {
      if (!map.current) {
        console.warn("Map not available for highlighting");
        return;
      }

      // Track this highlight for persistence across style changes
      activeHighlightRef.current = geometry;

      // Don't show polygons if setting is disabled
      if (!showPolygons) {
        return;
      }

      // If style hasn't loaded at all, wait for 'style.load'
      if (!map.current.getStyle()) {
        map.current.once("style.load", () => {
          highlightGeoJSON(geometry);
        });
        return;
      }

      if (!geometry) {
        console.warn("No geometry to highlight");
        return;
      }

      try {
        // Ensure map is settle enough for source addition
        if (!map.current.isStyleLoaded()) {
           map.current.once('idle', () => {
             // Re-check if this is still the active geometry before drawing
             if (activeHighlightRef.current === geometry) {
               highlightGeoJSON(geometry);
             }
           });
           return;
        }

        // Remove existing highlight if any
        if (map.current.getSource("highlighted-polygon")) {
          if (map.current.getLayer("highlighted-polygon-fill")) map.current.removeLayer("highlighted-polygon-fill");
          if (map.current.getLayer("highlighted-polygon-outline")) map.current.removeLayer("highlighted-polygon-outline");
          map.current.removeSource("highlighted-polygon");
        }

        // Create a Feature from the geometry
        const feature = {
          type: "Feature",
          geometry: geometry,
          properties: {},
        };

        // Add the polygon as a source
        map.current.addSource("highlighted-polygon", {
          type: "geojson",
          data: feature as any,
        });

        // Add fill layer
        map.current.addLayer({
          id: "highlighted-polygon-fill",
          type: "fill",
          source: "highlighted-polygon",
          paint: {
            "fill-color": [
              "interpolate",
              ["linear"],
              ["zoom"],
              0, "#003020",   // Darker at global view to compensate for ambient light
              6, "#004530",   // Transition
              10, "#006240"   // Intended color at street level
            ],
            "fill-opacity": 0.25,
            "fill-emissive-strength": 1, // Ensure visibility in Standard style night mode
          },
        });

        // Add outline layer
        map.current.addLayer({
          id: "highlighted-polygon-outline",
          type: "line",
          source: "highlighted-polygon",
          paint: {
            "line-color": "#2fa96c", // Mint green - softer outline
            "line-width": 2,
            "line-emissive-strength": 1, // Ensure visibility in Standard style night mode
          },
        });

        console.log("Successfully highlighted GeoJSON geometry");
      } catch (error) {
        console.warn(
          "Failed to add polygon highlight (context may be lost):",
          error
        );
      }
    };

    // Function to fit map bounds to a bbox (pre-computed from RPC)
    const fitToBbox = (bbox: { xmin: number; ymin: number; xmax: number; ymax: number }, padding: number = 50) => {
      if (!map.current) {
        console.warn("Map not available for fitting bounds");
        return;
      }

      const { xmin, ymin, xmax, ymax } = bbox;

      // Validate bbox values
      if (isNaN(xmin) || isNaN(ymin) || isNaN(xmax) || isNaN(ymax)) {
        console.warn("Invalid bbox values:", bbox);
        return;
      }

      // Create bounds and fit map
      const bounds = new mapboxgl.LngLatBounds(
        [xmin, ymin],
        [xmax, ymax]
      );

      map.current.fitBounds(bounds, {
        padding: padding,
        maxZoom: 12, // Don't zoom in too much for small polygons
        duration: 1000, // Smooth animation
      });

      console.log(`Fitted map to bbox: [${xmin}, ${ymin}] - [${xmax}, ${ymax}]`);
    };

    // Expose map methods via ref
    useImperativeHandle(ref, () => ({
      flyTo,
      getMap: () => map.current,
      highlightPolygon,
      highlightGeoJSON,
      fitToPolygons,
      fitToBbox,
      clearHighlight,
    }));

    return (
      <div ref={mapContainer} className={className} key="mapbox-container" />
    );
  }
);
