<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#10151a">
<meta name="description" content="KSEARCH — explorez le web par pays."><title>KSEARCH — Studio KG</title>
<link rel="icon" href="../logo-kgstudio.png"><link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Montserrat:wght@600;700;800&display=swap" rel="stylesheet"><link rel="stylesheet" href="./style.css?v=20261025004913">
</head>
<body>
<header class="topbar"><a class="studio" href="../index.html" aria-label="Studio KG"><img src="../logo-kgstudio.png" alt="" onerror="this.hidden=true"><span>STUDIO KG</span></a><a class="top-link" href="../index.html">Site principal <span aria-hidden="true">↗</span></a></header>
<main id="app" class="app">
<section class="search-area" aria-label="Rechercher sur le Web">
<div class="identity"><a class="ksearch-home-link" href="./" aria-label="Retour à l’accueil KSearch"></a><span class="identity-mark">K<span>✦</span></span><h1>KSEARCH</h1><p>Le monde à portée de recherche.</p></div>
<form id="form" class="search-shell" role="search">
<label class="sr-only" for="query">Votre recherche ou adresse web</label>
<input id="query" type="search" maxlength="180" placeholder="Rechercher sur le Web…" autocomplete="off" required>
<div class="search-actions"><div class="country-wrap"><label class="sr-only" for="country">Pays</label><span id="flag" aria-hidden="true">🌍</span><select id="country" aria-label="Choisir un pays"><option>Chargement…</option></select><span class="chevron" aria-hidden="true">↖</span></div><button class="submit" type="submit" aria-label="Lancer la recherche"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/></svg></button></div>
</form>
</section>
<section id="results-section" class="results-section" aria-label="Résultats de recherche" aria-live="polite" hidden><div class="results-meta"><span id="result-count">Résultats</span><span id="source-note"></span></div><div id="results" class="results"></div><nav id="pagination" class="pagination" aria-label="Pages de résultats" hidden><button id="previous" type="button">← Précédent</button><span id="page-label">Page 1</span><button id="next" type="button">Suivant →</button></nav></section>
</main><footer>© Studio KG · KSEARCH <span>Explorez, découvrez, naviguez.</span></footer><script src="./app.js" defer></script>
</body></html>
