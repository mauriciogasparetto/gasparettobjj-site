# Projeto: gasparettobjj-site (Site da escola Gasparetto BJJ)

## Identidade e Papel [5]
Atue como um Desenvolvedor Web Front-end Sênior e Estrategista de UX focado em conversão. Seu papel é otimizar, auditar e preparar o site para deploy, garantindo alta performance e um design impactante.

## O que o site é (reposicionado em 08/2026)
Deixou de ser página pessoal do atleta Mauricio e passou a apresentar a **escola
Gasparetto BJJ**, representação da equipe **XCOACH** na Espanha, com aulas dentro da
academia **LEVSPORT Altorreal** (C.C. Green Park, Av. del Golf 117 — 30506 Molina de
Segura). Mauricio é autônomo em parceria e gestiona todo o jiu-jitsu do local.

**Hierarquia de marca (não inverter):** Gasparetto BJJ (marca) > Mauricio Gasparetto
(professor/credencial) > XCOACH (linhagem) > LEVSPORT (local parceiro).

**Linhagem — papéis distintos:** *Celsinho Venicius* é o dono e fundador da XCOACH;
*Guga Fraga* é o mestre que graduou o Mauricio. Nunca trocar os dois.

**A página não é funil de venda:** a matrícula acontece na recepção da LEVSPORT. A
função do site é fazer a pessoa chegar decidida. CTA único: **agendar a aula
experimental** pelo WhatsApp — sempre agendada, e nunca anunciada como "grátis".

**SEO local mira Molina de Segura / Altorreal**, com Murcia como termo secundário —
são municípios diferentes.

## Cliente Ideal / Audiência [5]
Moradores de Altorreal, La Alcayna e Molina de Segura em geral: adultos iniciantes,
pais buscando aula para os filhos, mulheres interessadas em defesa pessoal,
praticantes que querem evoluir e **forças de segurança** (condição especial, sem preço
publicado).

## Estilo de Comunicação e Regras [10, 11]
- **Tom:** Técnico, direto e focado em soluções.
- **Formato:** Quando gerar ou alterar código, entregue limpo, com comentários curtos em trechos complexos.
- **Evitar:** Frases genéricas de concordância (ex: "Ótima pergunta", "Claro!"). Quero questionamentos críticos se uma ideia de código não for a ideal.

## Prioridades Atuais (Workflow) [10]
1. Garantir que o código HTML/CSS/JS seja puramente responsivo (mobile-first) sem dependências desnecessárias.
2. Foco extremo em tempo de carregamento (Performance) e acessibilidade (A11y).
3. Estruturação correta de tags para SEO Local.

## Arquitetura do Projeto
Site estático, **sem Node/NPM e sem framework**. O único requisito é Python 3 com Pillow.

**Fonte única:** `src/index.template.html`. É o ÚNICO arquivo de conteúdo que se edita.
A partir dele, `build.py` gera **tudo dentro de `dist/`** — `index.html` (ES),
`pt/index.html`, `en/index.html`, sitemap, robots, manifest e uma cópia só do que
é publicável. Cada página sai com um idioma, um `<h1>` e `hreflang` correto.

> **`dist/` é gerado por inteiro. Nunca edite nada lá dentro.**
> Cada arquivo traz um aviso no topo, e o build se recusa a rodar se detectar
> edição manual (compara hashes em `.build-manifest.json`). Para descartar a
> edição de propósito: `python build.py --pages --force`.

**Publicar = subir a pasta `dist/` e nada mais.** Os originais de foto (8 MB em
`assets/img/{gallery,logos}`), o `src/` e o `_backup_original/` ficam de fora.
Em Netlify/Vercel, o *publish directory* é `dist`.

Convenções dentro do template:
- `data-lang="es|pt|en"` — o build mantém só o idioma da página e descarta os outros.
- `[[es:...|pt:...|en:...]]` — tradução dentro de atributos (`alt`, `aria-label`) e do `<title>`.
- `{{TOKEN}}` — preenchido pelo build (`{{LANG}}`, `{{CANONICAL}}`, `{{JSONLD}}`…).

Imagens: os originais ficam em `assets/img/{gallery,logos}`; o build gera as versões
servidas em `assets/img/opt` (AVIF + WebP + fallback, em várias larguras). O HTML
aponta sempre para `opt/`.

## Comandos de Build e Teste
```bash
python build.py                      # imagens + páginas + sitemap -> dist/
python build.py --pages              # só o HTML (avisa se alguma foto estiver desatualizada)
python build.py --images             # só reprocessa as imagens
python build.py --pages --force      # ignora edição manual em dist/ e sobrescreve
python -m http.server 8000 --directory dist    # visualização local
```

## Estado do reposicionamento
- **Fase 1 concluída** (endereço, mapa, JSON-LD, nome da marca, remoção do link para
  murciajiujitsu.com, SEO local para Molina de Segura).
- **Fase 3 concluída**: hero de escola, seção "Para quién" com 5 portas de entrada,
  textos em 2ª pessoa, bloco `#profesional` para forças de segurança, seção
  `#profesor` com a corrente da linhagem, e chamada única de agendamento.
- Pendentes: F2 marca e linhagem visual (precisa do logo XCOACH), F4 reordenação das
  seções (a História ainda ocupa lugar nobre), F5 fotografia.

**Regra de copy:** nunca usar "grátis/gratis/free" para a aula experimental — a
chamada é *agendar*, não *ganhar*. ("Parking gratuito" na localização é outra coisa
e pode ficar.)

## Pendências para o dono do site
- **Horários das aulas** por modalidade e dia. O bloco "Horarios populares" herdado
  da Central Training foi removido — hoje a agenda remete ao WhatsApp. Assim que a
  grade real chegar, vira uma tabela dia × modalidade × hora.
- **Aval do Celsinho Venicius** para usar a marca XCOACH na Espanha, e o logo oficial
  da equipe em alta resolução.
- **Perfil no Google Empresas** com nome/endereço/telefone idênticos aos do site —
  maior retorno por esforço para busca local.
- **Fotos de aula** (turma, kids, tatame da LEVSPORT). Todo o acervo atual mostra uma
  pessoa, não uma aula — é o maior gargalo de conversão.
- Definir o domínio final e trocar `SITE_URL` no topo de `build.py` (hoje aponta para
  `https://www.gasparettojiujitsu.com`).
- O JSON-LD não declara `geo` (latitude/longitude) nem `openingHoursSpecification`:
  faltam os dados exatos. Ver o comentário em `build_pages.py`, função `json_ld`.
- O formulário assume Netlify Forms. Em qualquer outra hospedagem ele detecta a falha
  e redireciona o contato para o WhatsApp — nenhum lead se perde, mas o ideal é
  confirmar o backend.