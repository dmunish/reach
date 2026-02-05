import { useEffect, useRef, forwardRef, useImperativeHandle } from "react";
import mapboxgl from "mapbox-gl";
import customStyle from "./style.json";

export interface MapProps {
  accessToken: string;
  center?: [number, number];
  zoom?: number;
  theme?: string;
  showPolygons?: boolean;
  enableClustering?: boolean;
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
      enableClustering = false,
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

    // Constants for source and layers
    const MARKERS_SOURCE_ID = "alerts-markers-source";
    const PULSE_LAYER_ID = "alerts-pulse-layer";
    const POINT_LAYER_ID = "alerts-point-layer";

    // Clustering Configuration
    const CLUSTER_RADIUS = 20; // Reduced distance: Pins stay separate longer
    const CLUSTER_MAX_ZOOM = 14; 

    // Setup function for marker sources and layers
    const setupMarkersLayer = () => {
      if (!map.current) return;

      // Add source with clustering conditionally based on enableClustering prop
      if (!map.current.getSource(MARKERS_SOURCE_ID)) {
        map.current.addSource(MARKERS_SOURCE_ID, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
          cluster: enableClustering,
          clusterMaxZoom: CLUSTER_MAX_ZOOM,
          clusterRadius: CLUSTER_RADIUS,
        });
      }

      // Add animated pulse image
      if (!map.current.hasImage("pulsing-dot")) {
        const size = 150; // Increased base size
        const pulsingDot = {
          width: size,
          height: size,
          data: new Uint8Array(size * size * 4),

          onAdd: function () {
            const canvas = document.createElement("canvas");
            canvas.width = this.width;
            canvas.height = this.height;
            this.context = canvas.getContext("2d");
          },

          render: function () {
            const duration = 2000;
            const t = (performance.now() % duration) / duration;

            const radius = (size / 2) * 0.3;
            const outerRadius = (size / 2) * 0.7 * t + radius;
            const context = this.context;

            context.clearRect(0, 0, this.width, this.height);
            context.beginPath();
            context.arc(this.width / 2, this.height / 2, outerRadius, 0, Math.PI * 2);
            context.fillStyle = `rgba(255, 255, 255, ${0.4 * (1 - t)})`;
            context.fill();

            // update this image's data with data from the canvas
            this.data = context.getImageData(0, 0, this.width, this.height).data;
            map.current?.triggerRepaint();
            return true;
          },
        };
        map.current.addImage("pulsing-dot", pulsingDot as any, { pixelRatio: 2 });
      }

      // 1. Clusters Circle Layer (Stylized colors for counts) - only visible when clustering is enabled
      if (!map.current.getLayer("clusters")) {
        map.current.addLayer({
          id: "clusters",
          type: "circle",
          source: MARKERS_SOURCE_ID,
          filter: ["has", "point_count"],
          paint: {
            "circle-color": [
              "step",
              ["get", "point_count"],
              "rgba(30, 144, 255, 0.7)", // default blue
              10,
              "rgba(255, 140, 0, 0.7)",  // 10+ points orange
              30,
              "rgba(220, 20, 60, 0.7)",  // 30+ points red
            ],
            "circle-radius": [
              "step",
              ["get", "point_count"],
              20, 10, 25, 30, 35
            ],
            "circle-stroke-width": 2,
            "circle-stroke-color": "rgba(255, 255, 255, 0.3)",
          },
          layout: {
            "visibility": enableClustering ? "visible" : "none"
          }
        });
      }

      // 2. Cluster Count Text - only visible when clustering is enabled
      if (!map.current.getLayer("cluster-count")) {
        map.current.addLayer({
          id: "cluster-count",
          type: "symbol",
          source: MARKERS_SOURCE_ID,
          filter: ["has", "point_count"],
          layout: {
            "text-field": "{point_count_abbreviated}",
            "text-font": ["DIN Offc Pro Medium", "Arial Unicode MS Bold"],
            "text-size": 12,
            "visibility": enableClustering ? "visible" : "none"
          },
          paint: { "text-color": "#ffffff" },
        });
      }

      // 3. Pulse Animation (Unclustered)
      if (!map.current.getLayer("pulse-animation")) {
        map.current.addLayer({
          id: "pulse-animation",
          type: "symbol",
          source: MARKERS_SOURCE_ID,
          filter: ["!", ["has", "point_count"]],
          layout: {
            "icon-image": "pulsing-dot",
            "icon-size": ["interpolate", ["linear"], ["zoom"], 3, 0.6, 12, 1.0], // Increased icon size
            "icon-allow-overlap": true,
            "icon-ignore-placement": true,
          },
        });
      }

      // 4. Sharp Pin (Unclustered)
      if (!map.current.getLayer(POINT_LAYER_ID)) {
        map.current.addLayer({
          id: POINT_LAYER_ID,
          type: "circle",
          source: MARKERS_SOURCE_ID,
          filter: ["!", ["has", "point_count"]],
          paint: {
            "circle-radius": 8,
            "circle-color": ["get", "mainColor"],
            "circle-stroke-width": 2,
            "circle-stroke-color": "rgba(255, 255, 255, 0.8)", // More visible stroke
          },
        });
      }

      // Interaction listeners
      map.current.on("mouseenter", POINT_LAYER_ID, (e) => {
        if (map.current) map.current.getCanvas().style.cursor = "pointer";
        
        // Trigger hover callback for geometry prefetching
        const props = e.features?.[0].properties;
        const marker = markersDataRef.current?.[props?.index];
        if (marker?.onHover) {
          marker.onHover();
        }
      });
      map.current.on("mouseenter", "clusters", () => {
        if (map.current) map.current.getCanvas().style.cursor = "pointer";
      });
      map.current.on("mouseleave", POINT_LAYER_ID, () => {
        if (map.current) map.current.getCanvas().style.cursor = "";
      });
      map.current.on("mouseleave", "clusters", () => {
        if (map.current) map.current.getCanvas().style.cursor = "";
      });

      map.current.on("click", "clusters", (e) => {
        const features = map.current?.queryRenderedFeatures(e.point, { layers: ["clusters"] });
        const clusterId = features?.[0].properties?.cluster_id;
        const source = map.current?.getSource(MARKERS_SOURCE_ID) as mapboxgl.GeoJSONSource;
        source.getClusterExpansionZoom(clusterId, (err, zoom) => {
          if (err || !map.current) return;
          map.current.easeTo({
            center: (features?.[0].geometry as any).coordinates,
            zoom: zoom || map.current.getZoom() + 1,
          });
        });
      });

      map.current.on("click", POINT_LAYER_ID, (e) => {
        const props = e.features?.[0].properties;
        const marker = markersDataRef.current?.[props?.index];
        if (marker?.onClick) marker.onClick();
      });
    };

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
        setupMarkersLayer(); // Restore layers
      });

      // Add navigation controls
      map.current.addControl(new mapboxgl.NavigationControl(), "top-left");

      // Set up markers layer when map loads
      map.current.on("load", () => {
        setupMarkersLayer();
      });

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
      
      // Re-setup layers after style change
      map.current.once("style.load", () => {
        setupMarkersLayer();
        // Trigger a markers update to refill the data
        const markersSource = map.current?.getSource(MARKERS_SOURCE_ID) as mapboxgl.GeoJSONSource;
        if (markersSource) {
          // data update will be handled by the markers useEffect
        }
      });
    }, [theme]);

    // Update markers when markers prop changes
    useEffect(() => {
      if (!map.current) return;
      
      markersDataRef.current = markers;

      // Severity color mapping
      const getSeverityColors = (severity?: string): { main: string; pulse: string } => {
        switch (severity?.toLowerCase()) {
          case 'extreme':
            return { main: 'rgba(180, 0, 255, 1.0)', pulse: 'rgba(180, 0, 255, 1.0)' };
          case 'severe':
            return { main: 'rgba(220, 20, 60, 1.0)', pulse: 'rgba(220, 20, 60, 1.0)' };
          case 'moderate':
            return { main: 'rgba(255, 140, 0, 1.0)', pulse: 'rgba(255, 140, 0, 1.0)' };
          case 'minor':
            return { main: 'rgba(255, 215, 0, 1.0)', pulse: 'rgba(255, 215, 0, 1.0)' };
          case 'user':
            return { main: 'rgba(30, 144, 255, 1.0)', pulse: 'rgba(30, 144, 255, 0)' };
          default:
            return { main: 'rgba(30, 144, 255, 1.0)', pulse: 'rgba(30, 144, 255, 1.0)' };
        }
      };

      const updateMarkers = () => {
        if (!map.current) return;
        
        const source = map.current.getSource(MARKERS_SOURCE_ID) as mapboxgl.GeoJSONSource;
        if (!source) {
          // If source doesn't exist yet, wait/setup
          setupMarkersLayer();
          return;
        }

        const features: GeoJSON.Feature[] = markers.map((marker, index) => {
          const colors = getSeverityColors(marker.severity);
          return {
            type: "Feature",
            geometry: {
              type: "Point",
              coordinates: marker.coordinates,
            },
            properties: {
              index,
              severity: marker.severity,
              mainColor: colors.main,
              pulseColor: colors.pulse,
            },
          };
        });

        source.setData({
          type: "FeatureCollection",
          features: features,
        });
      };

      if (map.current.isStyleLoaded()) {
        updateMarkers();
      } else {
        map.current.once("load", updateMarkers);
      }
    }, [markers]);

    // Handle clustering changes dynamically
    useEffect(() => {
      if (!map.current || !map.current.isStyleLoaded()) return;

      const source = map.current.getSource(MARKERS_SOURCE_ID) as mapboxgl.GeoJSONSource;
      if (!source) return;

      // Update visibility of cluster-related layers
      try {
        const clusterLayerIds = ["clusters", "cluster-count"];
        clusterLayerIds.forEach(layerId => {
          if (map.current?.getLayer(layerId)) {
            map.current.setLayoutProperty(
              layerId,
              "visibility",
              enableClustering ? "visible" : "none"
            );
          }
        });

        // We need to reconfigure the source to enable/disable clustering
        // Store current data
        const currentData = (source as any)._data || { type: "FeatureCollection", features: [] };
        
        // Remove all layers that use this source
        const layersToRemove = ["clusters", "cluster-count", "pulse-animation", POINT_LAYER_ID];
        layersToRemove.forEach(layerId => {
          if (map.current?.getLayer(layerId)) {
            map.current.removeLayer(layerId);
          }
        });

        // Remove the source
        if (map.current.getSource(MARKERS_SOURCE_ID)) {
          map.current.removeSource(MARKERS_SOURCE_ID);
        }

        // Re-add source with new clustering configuration
        map.current.addSource(MARKERS_SOURCE_ID, {
          type: "geojson",
          data: currentData,
          cluster: enableClustering,
          clusterMaxZoom: CLUSTER_MAX_ZOOM,
          clusterRadius: CLUSTER_RADIUS,
        });

        // Re-add all layers with correct visibility
        setupMarkersLayer();
      } catch (error) {
        console.warn("Failed to update clustering configuration:", error);
      }
    }, [enableClustering]);

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

      // Don't show polygons if setting is disabled
      if (!showPolygons) {
        console.log("Polygon display is disabled in settings");
        return;
      }

      // Wait for map to be fully loaded
      if (!map.current.isStyleLoaded()) {
        console.log("Map style not loaded yet, waiting...");
        map.current.once("styledata", () => {
          highlightGeoJSON(geometry);
        });
        return;
      }

      if (!geometry) {
        console.warn("No geometry to highlight");
        return;
      }

      console.log("Highlighting GeoJSON geometry:", geometry);

      try {
        // Remove existing highlight if any
        clearHighlight();

        // Check if map is still valid before adding layers
        if (!map.current.getStyle()) {
          console.warn("Map style not available, skipping polygon highlight");
          return;
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
