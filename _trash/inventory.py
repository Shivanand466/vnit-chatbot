"""Decides which crawled vnit.ac.in page becomes which page of the website.

Reads the header of every page file in vnit-chatbot/data/raw/ (not the doc_
files, which are documents) and writes content/pages.json, plus
content/left_out.json for files that don't become a page and why. Every page
file must end up in exactly one of the two; the script stops if one doesn't.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
RAW = HERE.parent / "vnit-chatbot" / "data" / "raw"
CONTENT = HERE / "content"

SECTIONS = {
    "about": "About",
    "administration": "Administration",
    "academics": "Academics",
    "admissions": "Admissions",
    "departments": "Departments",
    "research": "Research",
    "students": "Students",
    "placements": "Placements",
    "news": "News and events",
    "recruitment": "Recruitment",
    "more": "More",
}

# raw file name (without .txt) -> (section key, slug inside the section)
PAGES = {
    "history": ("about", "history"),
    "general_information": ("about", "general-information"),
    "director": ("about", "director"),
    "nit_acts_statutes": ("about", "nit-acts-statutes"),
    "immovable_property_details_3": ("about", "immovable-property-details"),

    "registrar": ("administration", "registrar"),
    "deans_2026": ("administration", "deans"),
    "bog_2026": ("administration", "board-of-governors"),
    "administrative_officers": ("administration", "administrative-officers"),
    "head_of_departments": ("administration", "head-of-departments"),
    "director_office_staff": ("administration", "director-office-staff"),
    "technical_other_cadre_officers": ("administration", "technical-other-cadre-officers"),
    "building_works_committee": ("administration", "building-works-committee"),

    "academic_programs": ("academics", "academic-programs"),
    "academic_calendar": ("academics", "academic-calendar"),
    "section_academics": ("academics", "academic-section"),

    "admissions": ("admissions", "admission"),
    "fees": ("admissions", "fees"),

    "architecture_department": ("departments", "arch"),
    "chemical_department": ("departments", "chemical"),
    "civil_department": ("departments", "civil"),
    "cse_department": ("departments", "cse"),
    "ece_department": ("departments", "ece"),
    "eee_department": ("departments", "electrical"),
    "mech_department": ("departments", "mech"),
    "engineering_mining": ("departments", "mining"),
    "engineering_apm": ("departments", "apm"),
    "engineering_cvlsi": ("departments", "cvlsi"),
    "basic_science_chemistry": ("departments", "chemistry"),
    "basic_science_maths": ("departments", "maths"),
    "basic_science_hum": ("departments", "hum"),

    "section_rnc_coe_research_labs": ("research", "coe-research-labs"),
    "section_rnc_forms_annexures": ("research", "forms-annexures"),
    "section_rnc_ipr_innovation": ("research", "ipr-innovation"),
    "section_rnc_sponsored_research": ("research", "sponsored-research"),
    "index_php_patents": ("research", "patents"),
    "5g_lab_vnit_nagpur": ("research", "5g-lab"),
    "centre_for_innovation": ("research", "centre-for-innovation"),
    "technology_transfer": ("research", "technology-transfer"),
    "ongoing_research_collaborations": ("research", "ongoing-research-collaborations"),
    "s_tic_vnit": ("research", "s-tic"),
    "ciwg": ("research", "ciwg"),
    "entrepreneurship": ("research", "entrepreneurship"),

    "hostel": ("students", "hostel"),
    "section_hostel_fees": ("students", "hostel-fees"),
    "section_hostel_hostels": ("students", "hostels"),
    "section_hostel_notices": ("students", "hostel-notices"),
    "international_hostel_nonsaarc": ("students", "non-saarc"),
    "student_activity_clubs_vnit": ("students", "student-activity-clubs"),
    "section_sports": ("students", "sports"),
    "students_events": ("students", "students-events"),
    "library": ("students", "library"),
    "network_centre": ("students", "network-centre"),
    "section_uba": ("students", "uba"),

    "placements": ("placements", "training-and-placement"),

    "index_php_category_news": ("news", "news"),
    "index_php_category_news_events": ("news", "news-and-events"),
    "category_events": ("news", "events"),
    "ia_events": ("news", "ia-events"),
    "iaa_news": ("news", "iaa-news"),
    "_f0_9f_8e_93_vnit_nagpur_24th_convocation_2026": ("news", "24th-convocation-2026"),
    "instructions_to_degree_recipients_for_attending_24th_convocation_2026":
        ("news", "convocation-2026-instructions"),
    "vnit_nagpur_inspires_freshers_with_purpose_driven_education_healthy_living_and_c":
        ("news", "freshers-purpose-driven-education"),
    "vnit_nagpur_promotes_holistic_wellness_mindfulness_and_a_substance_free_life_amo":
        ("news", "holistic-wellness"),
    "vnit_nagpur_welcomes_the_new_batch_of_b_tech_b_arch_students_orientation_program":
        ("news", "orientation-programme-2026"),

    "recruitment": ("recruitment", "recruitment"),
    "recruitment_rules": ("recruitment", "recruitment-rules"),
    "recruitment_of_assistant_professor": ("recruitment", "assistant-professor"),
    "recruitment_of_associate_professor_at_vnit_nagpur": ("recruitment", "associate-professor"),
    "recruitment_of_professor_at_vnit_nagpur": ("recruitment", "professor"),

    "rti": ("more", "rti"),
    "section_stores": ("more", "stores"),
    "vrjscoe": ("more", "vrjscoe"),
    "telephone_directory": ("more", "telephone-directory"),
    "contact_us": ("more", "contact"),
}

# Pages built specially (not as ordinary content pages).
SPECIAL = {
    "home": "index.html (home page)",
    "notices": "home page and notices.html (the notice list)",
}

LEFT_OUT = {
    "faculty_recruitment_2025_shortlisted_candidates":
        "lists named individual candidates (privacy rule in Runbook 8)",
    "recruitmen":
        "same page as recruitment.txt (identical text, crawled at a second address)",
    "section_academics_notice_new":
        "same page as notices.txt (identical text, crawled at a second address)",
    "index_php_category_events":
        "same page as category_events.txt (identical text, crawled at a second address)",
}

# Short, readable menu titles where the crawled <title> is long or misspelt.
TITLES = {
    "architecture_department": "Architecture and Planning",
    "basic_science_chemistry": "Chemistry",
    "basic_science_hum": "Humanities and Social Sciences",
    "basic_science_maths": "Mathematics",
    "chemical_department": "Chemical Engineering",
    "civil_department": "Civil Engineering",
    "cse_department": "Computer Science and Engineering",
    "ece_department": "Electronics and Communication Engineering",
    "eee_department": "Electrical Engineering",
    "engineering_apm": "Applied Mechanics",
    "engineering_cvlsi": "Centre for VLSI and Nanotechnology",
    "engineering_mining": "Mining Engineering",
    "mech_department": "Mechanical Engineering",
    "admissions": "Admission",
    "fees": "Fees",
    "hostel": "Hostel Section",
    "section_hostel_fees": "Hostel Fees",
    "section_hostel_hostels": "Hostels",
    "section_hostel_notices": "Hostel Notices",
    "section_academics": "Academic and Exam Section",
    "placements": "Training and Placement",
    "section_sports": "Sports Section",
    "section_stores": "Store Section",
    "section_uba": "Unnat Bharat Abhiyan",
    "section_rnc_coe_research_labs": "CoE and Research Labs",
    "section_rnc_forms_annexures": "Forms and Annexures",
    "section_rnc_ipr_innovation": "IPR and Innovation",
    "section_rnc_sponsored_research": "Sponsored Research",
    "index_php_category_news": "News",
    "index_php_category_news_events": "News and Events",
    "category_events": "Events",
    "director": "Director",
    "international_hostel_nonsaarc": "International Hostel (Non-SAARC)",
    "_f0_9f_8e_93_vnit_nagpur_24th_convocation_2026": "24th Convocation 2026",
    "instructions_to_degree_recipients_for_attending_24th_convocation_2026":
        "Instructions to Degree Recipients, 24th Convocation 2026",
    "vnit_nagpur_inspires_freshers_with_purpose_driven_education_healthy_living_and_c":
        "VNIT Nagpur Inspires Freshers with Purpose-Driven Education",
    "vnit_nagpur_promotes_holistic_wellness_mindfulness_and_a_substance_free_life_amo":
        "VNIT Nagpur Promotes Holistic Wellness and Mindfulness",
    "vnit_nagpur_welcomes_the_new_batch_of_b_tech_b_arch_students_orientation_program":
        "Orientation Programme 2026",
    "recruitment_of_assistant_professor": "Recruitment of Assistant Professor",
    "recruitment_of_associate_professor_at_vnit_nagpur": "Recruitment of Associate Professor",
    "recruitment_of_professor_at_vnit_nagpur": "Recruitment of Professor",
    "rti": "RTI Officer",
    "contact_us": "Contact Us",
    "5g_lab_vnit_nagpur": "5G Lab",
    "s_tic_vnit": "S-TIC VNIT",
}


def read_header(path):
    """The SOURCE_URL / TITLE / FETCHED lines at the top of a raw file."""
    header = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        header[key.strip()] = value.strip()
    return header


def page_files():
    return sorted(p for p in RAW.glob("*.txt") if not p.name.startswith("doc_"))


def build():
    pages, left_out = [], []
    for path in page_files():
        name = path.stem
        if name in LEFT_OUT:
            left_out.append({"raw_file": path.name, "reason": LEFT_OUT[name]})
            continue
        if name in SPECIAL:
            left_out.append({"raw_file": path.name, "reason": "special page: " + SPECIAL[name]})
            continue
        if name not in PAGES:
            sys.exit(f"{path.name} is neither a page nor left out: add it to PAGES or LEFT_OUT")
        header = read_header(path)
        section, slug = PAGES[name]
        pages.append({
            "slug": f"{section}/{slug}",
            "section": section,
            "title": TITLES.get(name, header["TITLE"]),
            "source_url": header["SOURCE_URL"],
            "fetched": header["FETCHED"],
            "raw_file": path.name,
        })
    return pages, left_out


def main():
    pages, left_out = build()
    accounted = {p["raw_file"] for p in pages} | {x["raw_file"] for x in left_out}
    assert accounted == {p.name for p in page_files()}, "some raw page files are unaccounted for"
    assert len(accounted) == len(pages) + len(left_out), "a raw file is listed twice"
    stale = set(PAGES) - {Path(p["raw_file"]).stem for p in pages}
    assert not stale, f"PAGES names files that don't exist: {stale}"

    CONTENT.mkdir(exist_ok=True)
    order = list(SECTIONS)
    pages.sort(key=lambda p: (order.index(p["section"]), list(PAGES).index(Path(p["raw_file"]).stem)))
    (CONTENT / "pages.json").write_text(json.dumps(pages, indent=1, ensure_ascii=False), encoding="utf-8")
    (CONTENT / "left_out.json").write_text(json.dumps(left_out, indent=1, ensure_ascii=False), encoding="utf-8")

    counts = Counter(p["section"] for p in pages)
    print(f"{len(page_files())} raw page files: {len(pages)} pages, {len(left_out)} left out or special")
    for key in SECTIONS:
        print(f"  {SECTIONS[key]:18} {counts[key]}")
    for x in left_out:
        print(f"  left out: {x['raw_file']}: {x['reason']}")


if __name__ == "__main__":
    main()
