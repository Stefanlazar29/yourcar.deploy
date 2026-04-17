export default function Home() {
  return (
    <main style={{ padding: "2rem", maxWidth: 640 }}>
      <h1>Mulberry (Next.js)</h1>
      <p>
        Acest modul folosește <code>@vercel/speed-insights/next</code> în{" "}
        <code>app/layout.tsx</code>. Activează Speed Insights în proiectul Vercel
        și deploy-ui acest app (ex. setează Root Directory la{" "}
        <code>apps/web</code>).
      </p>
      <p>
        Site-ul HTML static rămâne în rădăcina repo-ului; acest folder este
        opțional pentru rute React/Next.
      </p>
    </main>
  );
}
