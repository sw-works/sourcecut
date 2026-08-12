"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { feature as topologyFeature } from "topojson-client";
import type { FeatureCollection as GeoFeatureCollection } from "geojson";
import type { GeometryCollection, Topology } from "topojson-specification";
import countries from "world-atlas/countries-110m.json";
import styles from "../../app/odyssey/odyssey.module.css";

const API = "/sourcecut-api/api/v1";
type Node = {
  route_node_id: string;
  event_id: string;
  poetic_place_id: string;
  canonical_name: string;
  place_class: string;
  sequence_index: string;
  display_region: string;
  citation_ids: string[];
};
type Edge = {
  route_edge_id: string;
  from_node_id: string;
  to_node_id: string;
  edge_kind: string;
  certainty: string;
};
type Hypothesis = {
  hypothesis_id: string;
  title: string;
  author_or_tradition: string;
  description: string;
  scholarly_source_ids: string[];
  is_default: boolean;
};
type Feature = {
  id: string;
  geometry: { type: "Point"; coordinates: [number, number] } | null;
  properties: {
    poetic_place_id: string;
    canonical_name: string;
    place_class: string;
    hypothesis_id: string;
    identification_class: string;
    confidence: string;
    rationale: string;
    source_ids: string[];
    display_style: string;
  };
};

const COLORS: Record<string, string> = {
  secure_places: "#c78b38",
  berard: "#2c7873",
  bradford: "#8e5a75",
};

export default function VoyageMap() {
  const [graph, setGraph] = useState<{ nodes: Node[]; edges: Edge[] }>({
    nodes: [],
    edges: [],
  });
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [active, setActive] = useState<string[]>(["secure_places"]);
  const [features, setFeatures] = useState<Feature[]>([]);
  const [selected, setSelected] = useState<Node | Feature | null>(null);
  const [mode, setMode] = useState<"graph" | "map">("graph");
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([
      fetch(`${API}/maps/odyssey/graph`).then((r) => r.json()),
      fetch(`${API}/route-hypotheses`).then((r) => r.json()),
    ])
      .then(([g, h]) => {
        setGraph(g);
        setHypotheses(h);
      })
      .catch(() => setError("Voyage data is unavailable."));
  }, []);
  useEffect(() => {
    const query = active
      .map((item) => `hypotheses=${encodeURIComponent(item)}`)
      .join("&");
    fetch(`${API}/maps/odyssey/geojson?${query}`)
      .then((r) => r.json())
      .then((data) => setFeatures(data.features))
      .catch(() => setError("Geographic layers are unavailable."));
  }, [active]);
  const disagreements = useMemo(() => {
    const grouped = new globalThis.Map<string, Set<string>>();
    features.forEach((f) => {
      const key = f.properties.poetic_place_id;
      grouped.set(
        key,
        (grouped.get(key) ?? new Set()).add(f.properties.hypothesis_id),
      );
    });
    return [...grouped]
      .filter(([, ids]) => ids.size > 1)
      .map(([place]) => place);
  }, [features]);
  function toggle(id: string) {
    setActive((current) =>
      current.includes(id)
        ? current.filter((x) => x !== id)
        : current.length < 3
          ? [...current, id]
          : current,
    );
  }
  return (
    <div className={styles.voyagePage}>
      <header className={styles.voyageHero}>
        <p className={styles.eyebrow}>Sequence before coordinates</p>
        <h1>
          A voyage drawn
          <br />
          with uncertainty.
        </h1>
        <p>
          The graph says where the poem moves next. The map shows only authority
          locations and named geographic proposals.
        </p>
        <div>
          <button
            onClick={() => setMode("graph")}
            aria-pressed={mode === "graph"}
          >
            Voyage graph
          </button>
          <button onClick={() => setMode("map")} aria-pressed={mode === "map"}>
            Geographic map
          </button>
        </div>
      </header>
      <aside className={styles.mapControls}>
        <h2>Layers</h2>
        <label>
          <input
            type="checkbox"
            checked={active.includes("secure_places")}
            onChange={() => toggle("secure_places")}
          />
          <i style={{ background: COLORS.secure_places }} />
          Identified ancient places
        </label>
        {hypotheses
          .filter((h) => h.hypothesis_id !== "textual_sequence")
          .map((h) => (
            <label key={h.hypothesis_id}>
              <input
                type="checkbox"
                checked={active.includes(h.hypothesis_id)}
                onChange={() => toggle(h.hypothesis_id)}
              />
              <i style={{ background: COLORS[h.hypothesis_id] }} />
              {h.title}
            </label>
          ))}
        <p>
          Up to three layers. Agreement among selected layers is not scholarly
          consensus.
        </p>
        {disagreements.length > 0 && (
          <section>
            <strong>Selected layers differ</strong>
            <p>{disagreements.join(", ")}</p>
          </section>
        )}
      </aside>
      <section className={styles.voyageSurface}>
        {error && <p role="alert">{error}</p>}
        {mode === "graph" ? (
          <Graph nodes={graph.nodes} onSelect={setSelected} />
        ) : (
          <Map features={features} onSelect={setSelected} />
        )}
      </section>
      <section className={styles.mapTable}>
        <h2>Accessible route register</h2>
        <table>
          <thead>
            <tr>
              <th>Seq.</th>
              <th>Poetic place</th>
              <th>Class</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {graph.nodes.map((node) => (
              <tr key={node.route_node_id}>
                <td>{Number(node.sequence_index)}</td>
                <td>
                  <button onClick={() => setSelected(node)}>
                    {node.canonical_name}
                  </button>
                </td>
                <td>{node.place_class.replaceAll("_", " ")}</td>
                <td>
                  <Link href={citationLink(node.citation_ids[0])}>
                    Exact passage
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {selected && (
        <aside className={styles.mapDrawer}>
          <button
            onClick={() => setSelected(null)}
            aria-label="Close evidence drawer"
          >
            ×
          </button>
          {"properties" in selected ? (
            <>
              <p className={styles.eyebrow}>
                {selected.properties.identification_class}
              </p>
              <h2>{selected.properties.canonical_name}</h2>
              <p>{selected.properties.rationale}</p>
              <dl>
                <div>
                  <dt>Layer</dt>
                  <dd>{selected.properties.hypothesis_id}</dd>
                </div>
                <div>
                  <dt>Confidence</dt>
                  <dd>{selected.properties.confidence}</dd>
                </div>
                <div>
                  <dt>Geometry</dt>
                  <dd>
                    {selected.geometry
                      ? selected.geometry.coordinates.join(", ")
                      : "intentionally unlocated"}
                  </dd>
                </div>
              </dl>
              <p>Sources: {selected.properties.source_ids.join(", ")}</p>
            </>
          ) : (
            <>
              <p className={styles.eyebrow}>
                {selected.place_class.replaceAll("_", " ")}
              </p>
              <h2>{selected.canonical_name}</h2>
              <p>
                This graph node is authoritative for narrative sequence, not
                geographic placement.
              </p>
              <Link href={citationLink(selected.citation_ids[0])}>
                Open exact passage →
              </Link>
            </>
          )}
        </aside>
      )}
    </div>
  );
}

function Graph({
  nodes,
  onSelect,
}: {
  nodes: Node[];
  onSelect: (item: Node) => void;
}) {
  return (
    <div
      className={styles.routeGraph}
      role="list"
      aria-label="Odysseus voyage sequence"
    >
      {nodes.map((node, index) => (
        <div key={node.route_node_id} role="listitem">
          <button onClick={() => onSelect(node)}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{node.canonical_name}</strong>
            <small>
              {node.display_region === "beyond"
                ? "Beyond / unlocated"
                : node.place_class.replaceAll("_", " ")}
            </small>
          </button>
          {index < nodes.length - 1 && <i aria-hidden="true">→</i>}
        </div>
      ))}
    </div>
  );
}
function Map({
  features,
  onSelect,
}: {
  features: Feature[];
  onSelect: (item: Feature) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current) return;
    let disposed = false;
    let map: { remove: () => void } | null = null;
    void import("maplibre-gl").then((maplibregl) => {
      if (disposed || !container.current) return;
      const topology = countries as unknown as Topology<{
        countries: GeometryCollection;
      }>;
      const land = topologyFeature(
        topology,
        topology.objects.countries,
      ) as unknown as GeoFeatureCollection;
      const instance = new maplibregl.Map({
        container: container.current,
        center: [12, 38],
        zoom: 3,
        maxBounds: [
          [-12, 28],
          [38, 47],
        ],
        style: {
          version: 8,
          sources: { land: { type: "geojson", data: land } },
          layers: [
            {
              id: "water",
              type: "background",
              paint: { "background-color": "#dce4df" },
            },
            {
              id: "land",
              type: "fill",
              source: "land",
              paint: {
                "fill-color": "#efe9dc",
                "fill-outline-color": "#73817a",
              },
            },
          ],
        },
        attributionControl: false,
      });
      instance.addControl(
        new maplibregl.NavigationControl({ showCompass: false }),
        "top-right",
      );
      instance.addControl(
        new maplibregl.AttributionControl({
          compact: true,
          customAttribution:
            "Physical context: Natural Earth · Places: Pleiades CC BY 3.0",
        }),
      );
      features
        .filter((item) => item.geometry)
        .forEach((feature) => {
          const button = document.createElement("button");
          button.className = styles.mapMarker;
          button.style.setProperty(
            "--marker-color",
            COLORS[feature.properties.hypothesis_id] ?? "#555",
          );
          button.setAttribute(
            "aria-label",
            `${feature.properties.canonical_name}, ${feature.properties.identification_class}, ${feature.properties.hypothesis_id}`,
          );
          button.dataset.kind = feature.properties.identification_class;
          button.addEventListener("click", () => onSelect(feature));
          new maplibregl.Marker({ element: button })
            .setLngLat(feature.geometry!.coordinates)
            .addTo(instance);
        });
      map = instance;
    });
    return () => {
      disposed = true;
      map?.remove();
    };
  }, [features, onSelect]);
  return (
    <div className={styles.geoMap}>
      <div
        ref={container}
        className={styles.mapCanvas}
        aria-label="Bounded Mediterranean hypothesis map"
      />
      <p>
        No inferred sailing tracks · unlocated places remain in the graph and
        route register.
      </p>
    </div>
  );
}
function citationLink(urn: string) {
  const match = urn?.match(/:(\d+)\.(\d+)-(\d+)$/);
  return match
    ? `/odyssey/read/${match[1]}?lines=${match[2]}-${match[3]}`
    : "/odyssey/read/1";
}
