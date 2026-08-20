"""
doTERRA -- Generator chunkiv dlya vidsutnih produktiv
"""

import json
import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
PRODUCTS_DIR = PROJECT_ROOT / "src" / "content" / "products"
DOCS_DIR = PROJECT_ROOT / "src" / "content" / "docs"
ALL_CHUNKS_FILE = PROJECT_ROOT / "all_chunks.json"

sys.path.insert(0, str(PROJECT_ROOT))
from src.content.parser import DoterraMarkdownParser


def _list_to_md(items: list, bullet: str = "👑") -> str:
    lines = []
    for item in items:
        if isinstance(item, dict):
            title = item.get("title", "")
            desc = item.get("description", item.get("summary", ""))
            if title and desc:
                lines.append(f"{bullet} **{title}:** {desc}")
            elif title:
                lines.append(f"{bullet} {title}")
            elif desc:
                lines.append(f"{bullet} {desc}")
            else:
                text = " -- ".join(str(v) for v in item.values() if v)
                if text:
                    lines.append(f"{bullet} {text}")
        elif isinstance(item, str):
            stripped = item.strip()
            if stripped and stripped[0] in "👑▫️🔹💦•":
                lines.append(stripped)
            else:
                lines.append(f"{bullet} {stripped}" if stripped else "")
    return "\n".join(lines)


def _diffuser_blend_to_md(blend: dict) -> str:
    name = blend.get("name", "")
    drops = blend.get("drops", [])
    parts = [f"💦 **{name}:**"] if name else []
    for d in drops:
        oil = d.get("oil", "")
        amount = d.get("amount", "")
        parts.append(f"  • {oil} -- {amount} kr.")
    return "\n".join(parts)


def json_to_md(product: dict) -> str:
    slug = product.get("slug", "unknown")
    name_ua = product.get("name_ua", "").strip()
    name_en = product.get("name_en", "").strip()

    if name_ua.startswith("Kategoriia:") or name_ua.startswith("Категорія:") or len(name_ua) > 80:
        title = name_en or slug
    else:
        title = f"{name_ua} -- {name_en}" if name_ua and name_en else (name_ua or name_en or slug)

    sections = []
    sections.append(f"# {title}\n")

    ptype = product.get("type", "")
    variants = product.get("product_variants", [])
    if ptype:
        sections.append(f"**Тип:** {ptype}\n")
    if variants:
        var_lines = []
        for v in variants:
            if isinstance(v, dict):
                vname = v.get("name", "")
                vurl = v.get("url", "")
                if vname and vurl:
                    var_lines.append(f"- [{vname}]({vurl})")
                elif vname:
                    var_lines.append(f"- {vname}")
            elif isinstance(v, str):
                var_lines.append(f"- {v}")
        if var_lines:
            sections.append("**Варіанти продукту:**\n" + "\n".join(var_lines) + "\n")

    sections.append("---\n")

    short_desc = product.get("short_description", [])
    if short_desc:
        if isinstance(short_desc, list):
            sections.append("## Короткий опис\n")
            sections.append(_list_to_md(short_desc, "👑") + "\n")
            sections.append("---\n")
        elif isinstance(short_desc, str):
            sections.append("## Короткий опис\n")
            sections.append(short_desc + "\n")
            sections.append("---\n")

    origin = product.get("origin")
    if origin and isinstance(origin, dict):
        sections.append("## Походження та склад\n")
        desc_list = origin.get("description", [])
        if isinstance(desc_list, list):
            for d in desc_list:
                sections.append(f"👑 {d}\n")
        elif isinstance(desc_list, str):
            sections.append(desc_list + "\n")
        comp = origin.get("composition", {})
        if comp:
            compounds = comp.get("compounds", [])
            comp_desc = comp.get("description", "")
            if compounds:
                sections.append("**Склад:** " + ", ".join(compounds) + "\n")
            if comp_desc:
                sections.append(comp_desc + "\n")
        sections.append("---\n")

    composition_str = product.get("склад-та-ключові-інгредієнти")
    if composition_str and isinstance(composition_str, str):
        sections.append("## Склад та ключові інгредієнти\n")
        sections.append(composition_str + "\n")
        sections.append("---\n")

    phys = product.get("physical_effects", [])
    if phys and isinstance(phys, list):
        sections.append("## Вплив на фізичне тіло\n")
        sections.append(_list_to_md(phys, "▫️") + "\n")
        sections.append("---\n")

    emot = product.get("emotional_effects")
    if emot and isinstance(emot, dict):
        sections.append("## Вплив на емоційному рівні\n")
        removes = emot.get("removes", [])
        develops = emot.get("develops", [])
        if removes:
            sections.append("**Прибирає:**\n" + _list_to_md(removes, "▫️") + "\n")
        if develops:
            sections.append("**Розвиває:**\n" + _list_to_md(develops, "▫️") + "\n")
        sections.append("---\n")

    usage = product.get("usage")
    usage_str = product.get("спосіб-застосування")
    if usage and isinstance(usage, dict):
        sections.append("## Способи застосування\n")
        aromatic = usage.get("aromatic", [])
        topical = usage.get("topical", [])
        internal = usage.get("internal")
        if aromatic:
            sections.append("**Ароматичний метод:**\n" + _list_to_md(aromatic, "🔹") + "\n")
        if topical:
            sections.append("**Метод місцевого застосування:**\n" + _list_to_md(topical, "🔹") + "\n")
        if internal:
            if isinstance(internal, str):
                sections.append(f"**Внутрішній спосіб:**\n🔹 {internal}\n")
            elif isinstance(internal, list):
                sections.append("**Внутрішній спосіб:**\n" + _list_to_md(internal, "🔹") + "\n")
        sections.append("---\n")
    elif usage_str and isinstance(usage_str, str):
        sections.append("## Способи застосування\n")
        sections.append(usage_str + "\n")
        sections.append("---\n")

    indications = product.get("indications", [])
    if indications and isinstance(indications, list):
        sections.append("## Показання\n")
        sections.append(_list_to_md(indications, "👑") + "\n")
        sections.append("---\n")

    beauty = product.get("beauty_skincare", [])
    if beauty and isinstance(beauty, list):
        sections.append("## Краса та догляд за шкірою\n")
        sections.append(_list_to_md(beauty, "👑") + "\n")
        sections.append("---\n")

    facts = product.get("interesting_facts", [])
    if facts and isinstance(facts, list):
        sections.append("## Цікаві факти\n")
        sections.append(_list_to_md(facts, "👑") + "\n")
        sections.append("---\n")

    blends = product.get("diffuser_blends", [])
    if blends and isinstance(blends, list):
        sections.append("## Суміші для дифузора\n")
        blend_parts = []
        for b in blends:
            if isinstance(b, dict) and "drops" in b:
                blend_parts.append(_diffuser_blend_to_md(b))
            elif isinstance(b, str):
                blend_parts.append(b)
        sections.append("\n\n".join(blend_parts) + "\n")
        sections.append("---\n")

    research = product.get("research", [])
    if research and isinstance(research, list):
        sections.append("## Дослідження\n")
        for r in research:
            if isinstance(r, dict):
                title_r = r.get("title", "")
                source = r.get("source", "")
                year = r.get("year", "")
                summary = r.get("summary", "")
                url = r.get("url", "")
                line = f"👑 **{title_r}**"
                if source and year:
                    line += f" ({source}, {year})"
                elif source:
                    line += f" ({source})"
                sections.append(line + "\n")
                if summary:
                    sections.append(summary + "\n")
                if url:
                    sections.append(f"Джерело: {url}\n")
            elif isinstance(r, str):
                sections.append(f"👑 {r}\n")
        sections.append("---\n")

    quotes = product.get("expert_quotes", [])
    if quotes and isinstance(quotes, list):
        sections.append("## Рекомендації\n")
        for q in quotes:
            if isinstance(q, dict):
                author = q.get("author", "")
                qtitle = q.get("title", "")
                quote = q.get("quote", "")
                source_q = q.get("source", "")
                if quote:
                    sections.append(f"👑 {quote}\n")
                if author:
                    author_line = f"-- {author}"
                    if qtitle:
                        author_line += f", {qtitle}"
                    sections.append(author_line + "\n")
                if source_q:
                    sections.append(f"Джерело: {source_q}\n")
            elif isinstance(q, str):
                sections.append(f"👑 {q}\n")
        sections.append("---\n")

    drug_int = product.get("drug_interactions", [])
    if drug_int and isinstance(drug_int, list):
        sections.append("## Взаємодія з препаратами\n")
        sections.append(_list_to_md(drug_int, "🔹") + "\n")
        sections.append("---\n")

    dosage = product.get("dosage_guide")
    if dosage and isinstance(dosage, dict):
        sections.append("## Дозування\n")
        for key, val in dosage.items():
            if val and isinstance(val, str):
                key_map = {
                    "aromatic": "Ароматичний",
                    "topical": "Місцеве",
                    "internal": "Внутрішній",
                    "children": "Для дітей",
                    "notes": "Примітки",
                }
                label = key_map.get(key, key)
                sections.append(f"🔹 **{label}:** {val}\n")
        sections.append("---\n")

    add_info = product.get("additional_info")
    if add_info and isinstance(add_info, str):
        sections.append("## Додаткова інформація\n")
        sections.append(add_info + "\n")
        sections.append("---\n")

    compat = product.get("сумісність-з-іншими-продуктами-doterra")
    if compat and isinstance(compat, str):
        sections.append("## Сумісність з іншими продуктами\n")
        sections.append(compat + "\n")
        sections.append("---\n")

    precautions = product.get("precautions", [])
    if precautions and isinstance(precautions, list):
        clean_prec = [
            p for p in precautions
            if isinstance(p, str) and not p.startswith(">") and not p.startswith("#")
        ]
        if clean_prec:
            sections.append("## Запобіжні заходи\n")
            sections.append(_list_to_md(clean_prec, "🔹") + "\n")
            sections.append("---\n")

    contra = product.get("contraindications", [])
    if contra and isinstance(contra, list):
        sections.append("## Протипоказання\n")
        sections.append(_list_to_md(contra, "🔹") + "\n")
        sections.append("---\n")

    disclaimer = product.get("disclaimer")
    if disclaimer and isinstance(disclaimer, str):
        sections.append(f"> {disclaimer}\n")

    return "\n".join(sections)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--output", "-o", default=str(ALL_CHUNKS_FILE))
    ap.add_argument("--save-md", action="store_true")
    args = ap.parse_args()

    output_path = Path(args.output)

    existing_chunks = []
    existing_slugs = set()
    if output_path.exists():
        existing_chunks = json.loads(output_path.read_text(encoding="utf-8"))
        existing_slugs = {c["product_slug"] for c in existing_chunks}
        print(f"Loaded {len(existing_chunks)} existing chunks ({len(existing_slugs)} products)")

    json_files = sorted(PRODUCTS_DIR.glob("*.json"))
    missing = [f for f in json_files if f.stem not in existing_slugs]

    print(f"JSON files in products/: {len(json_files)}")
    print(f"Already in chunks:       {len(existing_slugs)}")
    print(f"Missing (to add):        {len(missing)}")

    if not missing:
        print("All products already chunked!")
        return

    print("\nMissing products:")
    for f in missing:
        print(f"  - {f.stem}")

    if args.dry_run:
        print("\n[--dry-run] No changes applied.")
        return

    parser = DoterraMarkdownParser()
    new_chunks = []
    stats = {"ok": 0, "skip": 0, "error": 0}

    for json_file in missing:
        slug = json_file.stem
        try:
            product = json.loads(json_file.read_text(encoding="utf-8"))
            if "slug" not in product:
                product["slug"] = slug

            md_text = json_to_md(product)

            if args.save_md:
                md_path = DOCS_DIR / f"{slug}.md"
                md_path.write_text(md_text, encoding="utf-8")

            chunks = parser.parse_text(md_text, product_slug=slug, source_file=str(json_file))

            if not chunks:
                print(f"  WARN [{slug}] -- 0 chunks")
                stats["skip"] += 1
                continue

            chunk_dicts = [c.to_dict() for c in chunks]
            new_chunks.extend(chunk_dicts)
            print(f"  OK   [{slug}] -- {len(chunks)} chunks")
            stats["ok"] += 1

        except Exception as e:
            print(f"  ERR  [{slug}] -- {e}")
            stats["error"] += 1

    if new_chunks:
        all_chunks = existing_chunks + new_chunks
        output_path.write_text(
            json.dumps(all_chunks, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\nAdded {len(new_chunks)} new chunks")
        print(f"Total chunks in file: {len(all_chunks)}")
        print(f"Saved to: {output_path}")
    else:
        print("\nNo new chunks added")

    print(f"\nSummary: OK={stats['ok']}, skip={stats['skip']}, errors={stats['error']}")


if __name__ == "__main__":
    main()
