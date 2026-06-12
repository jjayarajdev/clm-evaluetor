#!/usr/bin/env python3
"""
Generate a Hardware Procurement Contract between Vialto Partners and CompuServe
based on the PFRDA RFP for 14 laptops with buyback.
"""

from fpdf import FPDF
from datetime import date, timedelta


class ContractPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 100, 100)
            self.cell(
                0, 5,
                "Hardware Procurement Contract | Vialto Partners - CompuServe | Ref: VP/PROC/2026/LC-001",
                align="C",
            )
            self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, num, title):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(0, 51, 102)
        self.cell(0, 8, f"{num}. {title}", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def subsection_title(self, num, title):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(0, 51, 102)
        self.cell(0, 7, f"{num} {title}", new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet(self, text, indent=15):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        x = self.get_x()
        self.set_x(x + indent)
        self.cell(5, 5.5, "-")
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def numbered_item(self, num, text, indent=15):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        x = self.get_x()
        self.set_x(x + indent)
        self.cell(10, 5.5, f"{num}.")
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def table_row(self, cols, widths, bold=False, fill=False):
        style = "B" if bold else ""
        self.set_font("Helvetica", style, 9)
        if fill:
            self.set_fill_color(220, 230, 241)
        h = 6
        for i, (col, w) in enumerate(zip(cols, widths)):
            self.cell(w, h, str(col), border=1, fill=fill)
        self.ln(h)


def generate():
    pdf = ContractPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    effective_date = date(2026, 5, 15)
    delivery_deadline = effective_date + timedelta(weeks=4)
    warranty_end = effective_date.replace(year=effective_date.year + 5)
    contract_end = effective_date.replace(year=effective_date.year + 5)

    # =========================================================================
    # PAGE 1 - Title Page
    # =========================================================================
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 15, "HARDWARE PROCUREMENT CONTRACT", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 10, "Supply of Laptop Computers with Buyback of Old Equipment", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(15)

    pdf.set_draw_color(0, 51, 102)
    pdf.set_line_width(0.5)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(15)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "BETWEEN", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 8, "Vialto Partners LLC", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6, "(hereinafter referred to as the \"Buyer\")", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "AND", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 8, "CompuServe Technologies Private Limited", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6, "(hereinafter referred to as the \"Supplier\")", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, f"Contract Reference: VP/PROC/2026/LC-001", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Effective Date: {effective_date.strftime('%B %d, %Y')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Contract Value: USD 18,200.00", align="C", new_x="LMARGIN", new_y="NEXT")

    # =========================================================================
    # PAGE 2-3 - Recitals, Definitions, Scope
    # =========================================================================
    pdf.add_page()

    pdf.section_title("1", "RECITALS")
    pdf.body_text(
        "WHEREAS, Vialto Partners LLC (\"Buyer\"), a company incorporated under the laws of the "
        "State of Delaware, United States, with its principal office at 600 Third Avenue, New York, "
        "NY 10016, is engaged in the business of providing global mobility, tax, and immigration "
        "advisory services and requires procurement of laptop computers for its operational staff;"
    )
    pdf.body_text(
        "AND WHEREAS, CompuServe Technologies Private Limited (\"Supplier\"), a company incorporated "
        "under the Companies Act, 2013 (India), with its registered office at Plot No. 42, Sector 18, "
        "Gurugram, Haryana 122015, India, is engaged in the business of supply, installation, and "
        "maintenance of information technology hardware and peripherals;"
    )
    pdf.body_text(
        "AND WHEREAS, the Buyer invited proposals through Request for Proposal (RFP) dated "
        "March 15, 2026, for the supply of fourteen (14) new laptop computers and buyback of six (6) "
        "existing end-of-life laptops, and the Supplier submitted its bid dated April 10, 2026, which "
        "was evaluated and found to be technically compliant and commercially competitive;"
    )
    pdf.body_text(
        "NOW THEREFORE, in consideration of the mutual covenants and agreements hereinafter set "
        "forth, and for other good and valuable consideration, the receipt and sufficiency of which are "
        "hereby acknowledged, the Parties agree as follows:"
    )

    pdf.section_title("2", "DEFINITIONS AND INTERPRETATION")
    pdf.body_text(
        'In this Contract, unless the context otherwise requires, the following terms shall have '
        'the meanings ascribed to them below:'
    )
    definitions = [
        ('"Acceptance"', 'means the formal written confirmation by the Buyer that the Goods have been delivered, installed, tested, and found to conform to the Technical Specifications set out in Schedule A.'),
        ('"Contract Price"', 'means the total sum of USD 18,200.00 (Eighteen Thousand Two Hundred United States Dollars) payable by the Buyer to the Supplier for the Goods and Services, inclusive of all taxes, duties, shipping, insurance, and installation charges.'),
        ('"Delivery Date"', f'means {delivery_deadline.strftime("%B %d, %Y")}, being four (4) weeks from the Effective Date, by which all Goods must be delivered to the Delivery Location.'),
        ('"Delivery Location"', 'means the Buyer\'s office at 600 Third Avenue, New York, NY 10016, or such other location as the Buyer may designate in writing.'),
        ('"Goods"', 'means the fourteen (14) laptop computers and associated peripherals, software licenses, and accessories described in Schedule A.'),
        ('"Buyback Equipment"', 'means the six (6) used laptop computers described in Schedule B, to be collected and disposed of by the Supplier.'),
        ('"Performance Security"', 'means the bank guarantee or demand draft equal to 10% of the Contract Price (USD 1,820.00) to be furnished by the Supplier.'),
        ('"Warranty Period"', f'means the period of five (5) years commencing from the date of Acceptance, expiring on {warranty_end.strftime("%B %d, %Y")}.'),
    ]
    for term, defn in definitions:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 30, 30)
        # Write term inline with definition
        pdf.set_x(25)
        pdf.multi_cell(0, 5.5, f"{term} {defn}")
        pdf.ln(2)

    # =========================================================================
    # Scope of Supply
    # =========================================================================
    pdf.section_title("3", "SCOPE OF SUPPLY")

    pdf.subsection_title("3.1", "New Laptop Computers")
    pdf.body_text(
        "The Supplier shall supply, deliver, install, and commission fourteen (14) brand-new laptop "
        "computers conforming to the Technical Specifications set out in Schedule A. Each laptop "
        "shall be delivered in its original manufacturer packaging, with all accessories, power adapters, "
        "documentation, and software pre-installed and activated."
    )

    pdf.subsection_title("3.2", "Buyback of Old Equipment")
    pdf.body_text(
        "The Supplier shall collect and take possession of six (6) used laptop computers as described "
        "in Schedule B. The buyback value has been factored into the Contract Price. The Supplier shall "
        "ensure secure data destruction of all storage media in the Buyback Equipment in accordance "
        "with NIST SP 800-88 Guidelines for Media Sanitization, and shall provide a Certificate of "
        "Data Destruction for each unit within fifteen (15) business days of collection."
    )

    pdf.subsection_title("3.3", "Software Licensing")
    pdf.body_text(
        "Each laptop shall be delivered with the following software pre-installed and licensed:\n"
        "(a) Microsoft Windows 11 Professional (64-bit), OEM license;\n"
        "(b) Microsoft Office 2024 Professional, perpetual license (one license per laptop);\n"
        "(c) Latest manufacturer BIOS/firmware updates applied."
    )

    pdf.subsection_title("3.4", "Quantity Variation")
    pdf.body_text(
        "The Buyer reserves the right to increase or decrease the quantity of Goods by up to "
        "twenty-five percent (+/- 25%) of the original order quantity within twelve (12) months "
        "from the Effective Date, at the same unit price and terms. Any such variation shall be "
        "communicated in writing with a minimum of fifteen (15) business days' notice."
    )

    # =========================================================================
    # Technical Specifications (Schedule A)
    # =========================================================================
    pdf.add_page()
    pdf.section_title("4", "TECHNICAL SPECIFICATIONS (SCHEDULE A)")

    pdf.body_text(
        "Each of the fourteen (14) laptop computers shall meet or exceed the following minimum "
        "technical specifications:"
    )

    specs = [
        ("Processor", "Intel Core i7, 11th Generation or higher (different different different different different)"),
        ("RAM", "16 GB DDR4 (or DDR5), expandable to 32 GB"),
        ("Storage", "512 GB NVMe SSD (M.2 form factor)"),
        ("Display", '14.0" Full HD (1920 x 1080) IPS, anti-glare, 250 nits minimum'),
        ("Graphics", "Intel Iris Xe integrated or equivalent"),
        ("Operating System", "Microsoft Windows 11 Professional (64-bit), pre-activated"),
        ("Office Suite", "Microsoft Office 2024 Professional, perpetual license"),
        ("Connectivity", "Wi-Fi 6 (802.11ax), Bluetooth 5.0+, Gigabit Ethernet (RJ-45 or via adapter)"),
        ("Ports", "Minimum: 2x USB 3.0 Type-A, 1x USB Type-C, 1x HDMI, 1x 3.5mm audio jack"),
        ("Webcam", "HD 720p or higher, integrated with privacy shutter"),
        ("Battery", "Minimum 8 hours rated battery life (MobileMark or equivalent benchmark)"),
        ("Weight", "Not exceeding 1.8 kg (including battery)"),
        ("Security", "TPM 2.0, fingerprint reader or IR camera for Windows Hello"),
        ("Keyboard", "Full-size, backlit, spill-resistant"),
        ("Warranty", "5-year comprehensive on-site warranty including Accidental Damage Protection"),
        ("Manufacturer", "Dell, HP, or Lenovo (Tier-1 OEM only)"),
        ("Certification", "BIS certified, ENERGY STAR, EPEAT registered"),
    ]

    widths = [45, 130]
    pdf.table_row(["Parameter", "Specification"], widths, bold=True, fill=True)
    for param, spec in specs:
        # Fix the processor spec
        if param == "Processor":
            spec = "Intel Core i7, 11th Generation or higher, minimum 4 cores / 8 threads"
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(30, 30, 30)
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        pdf.cell(widths[0], 6, param, border=1)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(widths[1], 6, spec, border=1)
        pdf.ln(6)

    pdf.ln(3)

    # =========================================================================
    # Buyback Schedule (Schedule B)
    # =========================================================================
    pdf.section_title("5", "BUYBACK EQUIPMENT (SCHEDULE B)")

    pdf.body_text(
        "The Supplier shall collect the following six (6) used laptops from the Buyer's premises "
        "and provide a buyback credit as factored into the Contract Price:"
    )

    bw = [10, 50, 35, 35, 45]
    pdf.table_row(["#", "Make / Model", "Approx. Age", "Condition", "Serial / Asset Tag"], bw, bold=True, fill=True)
    buyback_items = [
        ("1", "Compaq 6710B", "~15 years", "Non-functional", "To be recorded at pickup"),
        ("2", "HP ProBook 4410S", "~13 years", "Non-functional", "To be recorded at pickup"),
        ("3", "Dell Latitude 6230", "~11 years", "End-of-life", "To be recorded at pickup"),
        ("4", "Dell Latitude 6230", "~11 years", "End-of-life", "To be recorded at pickup"),
        ("5", "HP ProBook 430 G2", "~9 years", "Functional/Slow", "To be recorded at pickup"),
        ("6", "HP ProBook 4530S", "~12 years", "Non-functional", "To be recorded at pickup"),
    ]
    for item in buyback_items:
        pdf.table_row(item, bw)

    pdf.ln(3)
    pdf.body_text(
        "The Supplier shall ensure complete and certified data destruction of all hard drives and "
        "storage media before disposal. A Certificate of Data Destruction conforming to NIST SP "
        "800-88 shall be provided within fifteen (15) business days of collection."
    )

    # =========================================================================
    # Contract Price and Payment
    # =========================================================================
    pdf.section_title("6", "CONTRACT PRICE AND PAYMENT TERMS")

    pdf.subsection_title("6.1", "Contract Price")
    pdf.body_text(
        "The total Contract Price for the supply of fourteen (14) laptop computers, inclusive of "
        "all software licenses, delivery, installation, warranty, and net of buyback credit for "
        "six (6) old laptops, is USD 18,200.00 (United States Dollars Eighteen Thousand Two Hundred "
        "Only). The unit price breakdown is as follows:"
    )

    pw = [90, 40, 45]
    pdf.table_row(["Item", "Qty", "Amount (USD)"], pw, bold=True, fill=True)
    pdf.table_row(["Laptop Computer (as per Schedule A)", "14", "19,600.00"], pw)
    pdf.table_row(["Microsoft Office 2024 Professional License", "14", "Included"], pw)
    pdf.table_row(["5-Year On-Site Warranty with ADP", "14", "Included"], pw)
    pdf.table_row(["Delivery, Installation & Configuration", "1 Lot", "Included"], pw)
    pdf.table_row(["Less: Buyback Credit (6 old laptops)", "6", "(1,400.00)"], pw)
    pdf.set_font("Helvetica", "B", 9)
    pdf.table_row(["TOTAL CONTRACT PRICE", "", "18,200.00"], pw, bold=True, fill=True)
    pdf.ln(3)

    pdf.subsection_title("6.2", "Payment Schedule")
    pdf.body_text(
        "Payment shall be made in United States Dollars by wire transfer to the Supplier's designated "
        "bank account as follows:"
    )
    pdf.bullet("100% of the Contract Price shall be payable within thirty (30) calendar days from the date of Acceptance, against submission of: (a) original invoice in duplicate; (b) delivery challan signed by the Buyer's authorized representative; (c) Acceptance Certificate; and (d) valid Performance Security.")
    pdf.bullet("No advance payment shall be made under this Contract.")
    pdf.bullet("The Buyer shall be entitled to deduct or withhold any taxes at source as required by applicable law.")

    pdf.subsection_title("6.3", "Late Payment")
    pdf.body_text(
        "If the Buyer fails to make payment within the stipulated period, the Supplier shall be entitled "
        "to charge simple interest at the rate of 1.5% per month on the outstanding amount, calculated "
        "from the due date until the date of actual payment."
    )

    # =========================================================================
    # Performance Security
    # =========================================================================
    pdf.section_title("7", "PERFORMANCE SECURITY")

    pdf.subsection_title("7.1", "Amount and Form")
    pdf.body_text(
        "Within ten (10) business days of execution of this Contract, the Supplier shall furnish a "
        "Performance Security of USD 1,820.00 (Ten Percent of the Contract Price) in the form of an "
        "irrevocable bank guarantee or demand draft from a scheduled commercial bank acceptable to the "
        "Buyer, valid for a period of six (6) months beyond the Warranty Period."
    )

    pdf.subsection_title("7.2", "Forfeiture")
    pdf.body_text(
        "The Performance Security may be forfeited by the Buyer, in whole or in part, if the "
        "Supplier: (a) fails to deliver the Goods by the Delivery Date; (b) fails to meet the "
        "Technical Specifications; (c) abandons the Contract; or (d) commits a material breach "
        "of any term of this Contract."
    )

    pdf.subsection_title("7.3", "Release")
    pdf.body_text(
        "The Performance Security shall be released within thirty (30) days of the expiry of the "
        "Warranty Period, provided no claims are pending against the Supplier."
    )

    # =========================================================================
    # Delivery and Acceptance
    # =========================================================================
    pdf.section_title("8", "DELIVERY, INSTALLATION, AND ACCEPTANCE")

    pdf.subsection_title("8.1", "Delivery Schedule")
    pdf.body_text(
        f"The Supplier shall deliver all fourteen (14) laptop computers to the Delivery Location "
        f"no later than {delivery_deadline.strftime('%B %d, %Y')} (four weeks from the Effective Date). "
        f"Delivery shall be made during business hours (9:00 AM to 5:00 PM EST, Monday through Friday) "
        f"with at least two (2) business days' prior notice to the Buyer's designated contact."
    )

    pdf.subsection_title("8.2", "Installation and Configuration")
    pdf.body_text(
        "The Supplier shall, at no additional cost: (a) unbox and physically inspect each laptop; "
        "(b) power on and complete initial Windows setup; (c) verify Microsoft Office activation; "
        "(d) connect to the Buyer's Wi-Fi network (credentials to be provided); (e) run a hardware "
        "diagnostic test and record results; (f) apply all pending Windows and firmware updates."
    )

    pdf.subsection_title("8.3", "Acceptance Testing")
    pdf.body_text(
        "Upon delivery and installation, the Buyer shall have five (5) business days to conduct "
        "Acceptance Testing. Acceptance Testing shall include verification of: (a) physical condition "
        "and completeness; (b) conformance to Technical Specifications; (c) software licensing; "
        "(d) functionality of all ports, peripherals, and features. If any laptop fails Acceptance "
        "Testing, the Supplier shall replace the defective unit within five (5) business days at "
        "no additional cost."
    )

    pdf.subsection_title("8.4", "Risk and Title")
    pdf.body_text(
        "Risk of loss or damage to the Goods shall pass to the Buyer upon Acceptance. Title to "
        "the Goods shall pass to the Buyer upon full payment of the Contract Price. Until payment "
        "in full, the Supplier retains legal title but grants the Buyer the right to use the Goods."
    )

    # =========================================================================
    # Warranty and Maintenance
    # =========================================================================
    pdf.section_title("9", "WARRANTY AND MAINTENANCE")

    pdf.subsection_title("9.1", "Warranty Period")
    pdf.body_text(
        f"The Supplier warrants that each laptop computer shall be free from defects in materials "
        f"and workmanship for a period of five (5) years from the date of Acceptance (the \"Warranty "
        f"Period\"), expiring on {warranty_end.strftime('%B %d, %Y')}. This warranty includes coverage "
        f"for Accidental Damage Protection (ADP) covering drops, spills, electrical surges, and "
        f"broken screens."
    )

    pdf.subsection_title("9.2", "Warranty Service Levels")
    pdf.body_text("During the Warranty Period, the Supplier shall provide the following service levels:")
    pdf.bullet("Response Time: The Supplier shall acknowledge any warranty service request within four (4) business hours of receipt.")
    pdf.bullet("Resolution Time: Hardware repairs or replacement shall be completed within two (2) business days of the service request for standard issues, and five (5) business days for ADP claims requiring parts replacement.")
    pdf.bullet("Service Mode: All warranty service shall be provided on-site at the Buyer's premises. The Supplier shall bear all costs of travel, parts, and labor.")
    pdf.bullet("Escalation: If a warranty issue is not resolved within the stipulated time, the matter shall be escalated to the Supplier's regional service manager within twenty-four (24) hours.")

    pdf.subsection_title("9.3", "Preventive Maintenance")
    pdf.body_text(
        "The Supplier shall conduct preventive maintenance visits every six (6) months during the "
        "Warranty Period (ten visits total). Each visit shall include: (a) hardware diagnostic scan; "
        "(b) thermal paste reapplication if needed; (c) firmware and driver updates; (d) battery "
        "health assessment; (e) physical cleaning of vents and keyboard. The Supplier shall provide "
        "a maintenance report after each visit."
    )

    pdf.subsection_title("9.4", "Replacement Policy")
    pdf.body_text(
        "If any laptop requires more than three (3) warranty repairs for the same component within "
        "any twelve (12) month period, the Supplier shall replace the entire unit with a new laptop "
        "of equivalent or higher specification at no additional cost to the Buyer."
    )

    # =========================================================================
    # SLAs
    # =========================================================================
    pdf.add_page()
    pdf.section_title("10", "SERVICE LEVEL AGREEMENT")

    pdf.body_text(
        "The Supplier shall meet the following Key Performance Indicators throughout the Contract "
        "term. Failure to meet these SLAs shall result in the corresponding service credits:"
    )

    sw = [55, 35, 40, 45]
    pdf.table_row(["Metric", "Target", "Measurement", "Penalty"], sw, bold=True, fill=True)
    sla_rows = [
        ("On-Time Delivery", "100%", "Per delivery event", "1% per week delay"),
        ("Acceptance Pass Rate", ">= 95%", "Per batch", "Replace at no cost"),
        ("Warranty Response", "<= 4 hours", "Per incident", "USD 50 per breach"),
        ("Warranty Resolution", "<= 2 bus. days", "Per incident", "USD 100 per breach"),
        ("ADP Resolution", "<= 5 bus. days", "Per ADP claim", "USD 100 per breach"),
        ("PM Visit Completion", "100% on-time", "Semi-annual", "USD 200 per missed"),
        ("Uptime (first year)", ">= 99%", "Per laptop/year", "Pro-rata credit"),
        ("Battery Health (Y3)", ">= 80% capacity", "Per laptop", "Battery replacement"),
    ]
    for row in sla_rows:
        pdf.table_row(row, sw)

    pdf.ln(3)

    pdf.subsection_title("10.1", "Liquidated Damages for Late Delivery")
    pdf.body_text(
        "If the Supplier fails to deliver the Goods by the Delivery Date, the Buyer shall, without "
        "prejudice to its other remedies, deduct from the Contract Price, as liquidated damages, "
        "a sum equivalent to 1% of the Contract Price (USD 182.00) for each week of delay or part "
        "thereof, subject to a maximum deduction of 10% of the Contract Price (USD 1,820.00). If "
        "the delay exceeds ten (10) weeks, the Buyer may terminate this Contract."
    )

    pdf.subsection_title("10.2", "Service Credit Cap")
    pdf.body_text(
        "The aggregate service credits and liquidated damages payable by the Supplier under this "
        "Contract in any twelve (12) month period shall not exceed 15% of the Contract Price."
    )

    # =========================================================================
    # Intellectual Property
    # =========================================================================
    pdf.section_title("11", "INTELLECTUAL PROPERTY AND SOFTWARE LICENSING")

    pdf.body_text(
        "The Supplier warrants that: (a) all Goods and software supplied under this Contract are "
        "genuine and legitimately sourced; (b) the Microsoft Windows and Microsoft Office licenses "
        "are perpetual, transferable, and validly activated; (c) no Goods infringe upon any third "
        "party's intellectual property rights. The Supplier shall indemnify and hold harmless the "
        "Buyer from any claims, damages, or expenses arising from any breach of this warranty."
    )

    # =========================================================================
    # Confidentiality
    # =========================================================================
    pdf.section_title("12", "CONFIDENTIALITY")

    pdf.body_text(
        "Each Party agrees to maintain the confidentiality of all non-public information received "
        "from the other Party in connection with this Contract, including but not limited to pricing, "
        "technical specifications, business plans, and employee data. This obligation shall survive "
        "the termination or expiry of this Contract for a period of three (3) years. The Supplier's "
        "obligation extends to ensuring secure data destruction of all information contained on the "
        "Buyback Equipment."
    )

    # =========================================================================
    # Termination
    # =========================================================================
    pdf.add_page()
    pdf.section_title("13", "TERMINATION")

    pdf.subsection_title("13.1", "Termination for Convenience")
    pdf.body_text(
        "The Buyer may terminate this Contract at any time by giving thirty (30) calendar days' "
        "written notice to the Supplier. In such event, the Buyer shall pay for all Goods delivered "
        "and accepted prior to the effective date of termination, and the Supplier shall refund any "
        "advance or excess payments within fifteen (15) business days."
    )

    pdf.subsection_title("13.2", "Termination for Cause")
    pdf.body_text(
        "Either Party may terminate this Contract immediately upon written notice if the other "
        "Party: (a) commits a material breach and fails to cure such breach within fifteen (15) "
        "business days of receiving written notice; (b) becomes insolvent, files for bankruptcy, "
        "or has a receiver appointed; (c) is found to have made any fraudulent misrepresentation."
    )

    pdf.subsection_title("13.3", "Effect of Termination")
    pdf.body_text(
        "Upon termination: (a) the Supplier shall immediately cease all work; (b) the Supplier "
        "shall return or destroy all Buyer Confidential Information; (c) all accrued rights and "
        "obligations (including warranty obligations for Goods already accepted) shall survive "
        "termination; (d) the Performance Security shall be handled as per Clause 7."
    )

    # =========================================================================
    # Indemnification and Limitation of Liability
    # =========================================================================
    pdf.section_title("14", "INDEMNIFICATION AND LIMITATION OF LIABILITY")

    pdf.subsection_title("14.1", "Indemnification")
    pdf.body_text(
        "The Supplier shall indemnify, defend, and hold harmless the Buyer, its officers, directors, "
        "employees, and agents from and against any and all claims, losses, damages, liabilities, "
        "costs, and expenses (including reasonable attorneys' fees) arising from or in connection "
        "with: (a) any defect in the Goods; (b) any breach of this Contract by the Supplier; "
        "(c) any infringement of third-party intellectual property rights; (d) any injury to persons "
        "or damage to property caused by the Goods; (e) any failure in data destruction of Buyback "
        "Equipment."
    )

    pdf.subsection_title("14.2", "Limitation of Liability")
    pdf.body_text(
        "Except in cases of gross negligence, willful misconduct, or breach of confidentiality "
        "obligations, neither Party's total aggregate liability under this Contract shall exceed "
        "the Contract Price. Neither Party shall be liable for any indirect, incidental, "
        "consequential, special, or punitive damages, including loss of profits, data, or business "
        "opportunity, even if advised of the possibility of such damages."
    )

    # =========================================================================
    # Force Majeure
    # =========================================================================
    pdf.section_title("15", "FORCE MAJEURE")
    pdf.body_text(
        "Neither Party shall be liable for any delay or failure to perform its obligations under "
        "this Contract to the extent that such delay or failure results from Force Majeure events "
        "including but not limited to: natural disasters, war, terrorism, pandemic, government "
        "sanctions, embargoes, or any event beyond the reasonable control of the affected Party. "
        "The affected Party shall: (a) notify the other Party in writing within five (5) business "
        "days; (b) use commercially reasonable efforts to mitigate the effects; (c) resume "
        "performance as soon as reasonably practicable. If a Force Majeure event continues for more "
        "than sixty (60) consecutive days, either Party may terminate this Contract without liability."
    )

    # =========================================================================
    # Sub-Contracting
    # =========================================================================
    pdf.section_title("16", "SUB-CONTRACTING AND ASSIGNMENT")
    pdf.body_text(
        "The Supplier shall not sub-contract, assign, or transfer any part of this Contract or "
        "any rights or obligations hereunder to any third party without the prior written consent "
        "of the Buyer. Any unauthorized sub-contracting or assignment shall be void and shall "
        "constitute a material breach of this Contract. Notwithstanding the foregoing, the Supplier "
        "may engage the original equipment manufacturer's authorized service partners for the "
        "purpose of fulfilling warranty obligations, provided the Supplier remains fully responsible "
        "for all obligations under this Contract."
    )

    # =========================================================================
    # Dispute Resolution and Governing Law
    # =========================================================================
    pdf.section_title("17", "DISPUTE RESOLUTION AND GOVERNING LAW")

    pdf.subsection_title("17.1", "Amicable Resolution")
    pdf.body_text(
        "The Parties shall attempt in good faith to resolve any dispute arising out of or in "
        "connection with this Contract through mutual consultation and negotiation within thirty "
        "(30) calendar days of either Party notifying the other of the dispute in writing."
    )

    pdf.subsection_title("17.2", "Mediation")
    pdf.body_text(
        "If the dispute is not resolved through amicable negotiation, the Parties agree to submit "
        "the dispute to mediation administered by the American Arbitration Association (AAA) under "
        "its Commercial Mediation Rules before pursuing arbitration or litigation."
    )

    pdf.subsection_title("17.3", "Arbitration")
    pdf.body_text(
        "If mediation fails to resolve the dispute within sixty (60) calendar days of the mediator's "
        "appointment, either Party may refer the dispute to binding arbitration administered by the "
        "AAA under its Commercial Arbitration Rules. The arbitration shall be conducted by a sole "
        "arbitrator in New York, New York. The language of arbitration shall be English. The "
        "arbitrator's award shall be final and binding on both Parties and may be entered as a "
        "judgment in any court of competent jurisdiction."
    )

    pdf.subsection_title("17.4", "Governing Law")
    pdf.body_text(
        "This Contract shall be governed by and construed in accordance with the laws of the State "
        "of New York, United States of America, without regard to its conflict of laws principles. "
        "The courts located in New York, New York shall have exclusive jurisdiction over any "
        "proceedings not subject to arbitration."
    )

    # =========================================================================
    # Insurance
    # =========================================================================
    pdf.section_title("18", "INSURANCE")

    pdf.subsection_title("18.1", "Supplier's Insurance")
    pdf.body_text(
        "The Supplier shall, at its own expense, maintain throughout the term of this Contract "
        "the following insurance coverage with reputable insurers acceptable to the Buyer:"
    )
    pdf.bullet("Commercial General Liability Insurance with a minimum coverage of USD 1,000,000 per occurrence and USD 2,000,000 in aggregate, covering bodily injury, property damage, and products liability.")
    pdf.bullet("Professional Indemnity / Errors & Omissions Insurance with a minimum coverage of USD 500,000 per claim, covering losses arising from the Supplier's professional services including installation, configuration, and maintenance.")
    pdf.bullet("Cyber Liability Insurance with a minimum coverage of USD 500,000 per occurrence, covering data breaches, unauthorized access to Buyer's systems, and costs associated with notification and remediation.")
    pdf.bullet("Workers' Compensation Insurance as required by applicable law for all Supplier personnel performing services at the Buyer's premises.")

    pdf.subsection_title("18.2", "Evidence of Insurance")
    pdf.body_text(
        "The Supplier shall provide certificates of insurance to the Buyer within ten (10) business "
        "days of execution of this Contract and annually thereafter. The Buyer shall be named as an "
        "additional insured on the Commercial General Liability and Cyber Liability policies. The "
        "Supplier shall provide at least thirty (30) days' prior written notice to the Buyer of any "
        "cancellation, material change, or non-renewal of any required insurance policy."
    )

    # =========================================================================
    # Data Protection
    # =========================================================================
    pdf.section_title("19", "DATA PROTECTION AND PRIVACY")

    pdf.subsection_title("19.1", "Data Processing")
    pdf.body_text(
        "To the extent that the Supplier processes any personal data of the Buyer's employees or "
        "clients in the performance of this Contract (including data stored on Buyback Equipment or "
        "accessed during warranty service), the Supplier shall: (a) process such data only on the "
        "documented instructions of the Buyer; (b) ensure that persons authorized to process the "
        "data have committed themselves to confidentiality; (c) implement appropriate technical and "
        "organizational measures to ensure the security of processing; (d) not engage another "
        "processor without the Buyer's prior written authorization."
    )

    pdf.subsection_title("19.2", "Data Breach Notification")
    pdf.body_text(
        "In the event of any actual or suspected unauthorized access to, disclosure of, or loss of "
        "Buyer personal data (a \"Data Breach\"), the Supplier shall: (a) notify the Buyer within "
        "twenty-four (24) hours of becoming aware of the Data Breach; (b) provide full details of "
        "the nature, scope, and likely consequences of the breach; (c) take immediate steps to contain "
        "and remediate the breach; (d) cooperate fully with the Buyer's investigation; (e) bear all "
        "reasonable costs associated with the breach response, including notification costs, credit "
        "monitoring services, and regulatory fines where the breach resulted from the Supplier's "
        "negligence."
    )

    pdf.subsection_title("19.3", "Cross-Border Data Transfers")
    pdf.body_text(
        "The Supplier shall not transfer any Buyer personal data outside the United States without "
        "the Buyer's prior written consent. Where cross-border transfer is authorized, the Supplier "
        "shall ensure that adequate safeguards are in place in accordance with applicable data "
        "protection laws, including standard contractual clauses or binding corporate rules."
    )

    # =========================================================================
    # Environmental and Sustainability
    # =========================================================================
    pdf.section_title("20", "ENVIRONMENTAL AND SUSTAINABILITY COMPLIANCE")

    pdf.subsection_title("20.1", "Environmental Standards")
    pdf.body_text(
        "The Supplier represents and warrants that all Goods supplied under this Contract comply "
        "with the following environmental standards and regulations: (a) ENERGY STAR certification "
        "for energy efficiency; (b) EPEAT (Electronic Product Environmental Assessment Tool) "
        "registered at Gold or Silver level; (c) RoHS (Restriction of Hazardous Substances) "
        "Directive compliance; (d) REACH (Registration, Evaluation, Authorisation and Restriction "
        "of Chemicals) regulation compliance where applicable."
    )

    pdf.subsection_title("20.2", "E-Waste Management")
    pdf.body_text(
        "The Supplier shall ensure that all Buyback Equipment and any defective components replaced "
        "during the Warranty Period are disposed of in accordance with applicable e-waste regulations, "
        "including the Resource Conservation and Recovery Act (RCRA) and any applicable state e-waste "
        "laws. The Supplier shall provide a Certificate of Environmentally Responsible Disposal for "
        "each batch of equipment disposed. Under no circumstances shall the Supplier export e-waste "
        "to countries that are not parties to the Basel Convention."
    )

    pdf.subsection_title("20.3", "Packaging")
    pdf.body_text(
        "The Supplier shall minimize packaging materials and use recyclable or biodegradable "
        "packaging wherever feasible. All packaging materials shall be free of ozone-depleting "
        "substances. The Supplier shall collect and responsibly dispose of all packaging materials "
        "after delivery and installation at the Delivery Location."
    )

    # =========================================================================
    # Change Management
    # =========================================================================
    pdf.section_title("21", "CHANGE MANAGEMENT")

    pdf.subsection_title("21.1", "Change Requests")
    pdf.body_text(
        "Either Party may propose changes to the scope, specifications, delivery schedule, or other "
        "terms of this Contract by submitting a written Change Request to the other Party. A Change "
        "Request shall include: (a) a detailed description of the proposed change; (b) the reason for "
        "the change; (c) the estimated impact on Contract Price, delivery schedule, and service levels; "
        "(d) any other relevant information."
    )

    pdf.subsection_title("21.2", "Evaluation and Approval")
    pdf.body_text(
        "The receiving Party shall evaluate the Change Request and respond in writing within ten (10) "
        "business days. No change shall be effective unless agreed in writing by both Parties through "
        "a formal Change Order signed by authorized representatives. The Supplier shall not commence "
        "any work related to a proposed change until a Change Order has been executed."
    )

    pdf.subsection_title("21.3", "Product Discontinuation")
    pdf.body_text(
        "If the manufacturer discontinues the specified laptop model during the term of this Contract "
        "(including the Quantity Variation period), the Supplier shall: (a) notify the Buyer immediately "
        "upon learning of the discontinuation; (b) propose an equivalent or superior replacement model "
        "at the same or lower unit price; (c) provide a detailed comparison of specifications between "
        "the original and proposed replacement; (d) obtain the Buyer's written approval before "
        "delivering the replacement model."
    )

    # =========================================================================
    # Representations and Warranties
    # =========================================================================
    pdf.section_title("22", "REPRESENTATIONS AND WARRANTIES")

    pdf.subsection_title("22.1", "Supplier Representations")
    pdf.body_text(
        "The Supplier represents and warrants that: (a) it is duly organized, validly existing, "
        "and in good standing under the laws of its jurisdiction of incorporation; (b) it has full "
        "corporate power and authority to enter into and perform this Contract; (c) the execution "
        "and performance of this Contract do not violate any law, regulation, or agreement to which "
        "the Supplier is a party; (d) it holds all licenses, permits, and authorizations required "
        "to perform its obligations under this Contract; (e) it is an authorized reseller of Dell, "
        "HP, and Lenovo products; (f) all Goods are new, unused, and of the most recent production "
        "batch available."
    )

    pdf.subsection_title("22.2", "Buyer Representations")
    pdf.body_text(
        "The Buyer represents and warrants that: (a) it is duly organized, validly existing, and "
        "in good standing under the laws of the State of Delaware; (b) it has full corporate power "
        "and authority to enter into and perform this Contract; (c) the Buyback Equipment is owned "
        "by the Buyer free and clear of all liens and encumbrances; (d) all data on the Buyback "
        "Equipment has been backed up by the Buyer prior to handover to the Supplier."
    )

    # =========================================================================
    # Anti-Corruption and Compliance (renumbered)
    # =========================================================================
    pdf.section_title("23", "ANTI-CORRUPTION AND COMPLIANCE")
    pdf.body_text(
        "The Supplier represents and warrants that: (a) it has not, and shall not, directly or "
        "indirectly, offer, pay, promise, or authorize the payment of any money or anything of "
        "value to any government official, political party, or public international organization "
        "for the purpose of influencing any act or decision to obtain or retain business; (b) it "
        "shall comply with all applicable anti-corruption laws including the U.S. Foreign Corrupt "
        "Practices Act (FCPA) and the UK Bribery Act 2010; (c) it shall maintain accurate books "
        "and records reflecting all transactions under this Contract."
    )

    # =========================================================================
    # General Provisions
    # =========================================================================
    pdf.section_title("24", "GENERAL PROVISIONS")

    pdf.subsection_title("24.1", "Entire Agreement")
    pdf.body_text(
        "This Contract, together with its Schedules, constitutes the entire agreement between the "
        "Parties with respect to the subject matter hereof and supersedes all prior negotiations, "
        "representations, warranties, commitments, offers, and agreements, whether written or oral."
    )

    pdf.subsection_title("24.2", "Amendments")
    pdf.body_text(
        "No amendment, modification, or waiver of any provision of this Contract shall be effective "
        "unless made in writing and signed by duly authorized representatives of both Parties."
    )

    pdf.subsection_title("24.3", "Notices")
    pdf.body_text(
        "All notices under this Contract shall be in writing and delivered by registered mail, "
        "courier, or email with read receipt to the following addresses:\n\n"
        "Buyer: Vialto Partners LLC, 600 Third Avenue, New York, NY 10016\n"
        "Attention: Procurement Manager | Email: procurement@vialto.com\n\n"
        "Supplier: CompuServe Technologies Pvt. Ltd., Plot 42, Sector 18, Gurugram 122015, India\n"
        "Attention: Contract Manager | Email: contracts@compuserve.in"
    )

    pdf.subsection_title("24.4", "Severability")
    pdf.body_text(
        "If any provision of this Contract is held to be invalid or unenforceable, the remaining "
        "provisions shall continue in full force and effect."
    )

    pdf.subsection_title("24.5", "Waiver")
    pdf.body_text(
        "The failure of either Party to enforce any right or provision of this Contract shall not "
        "constitute a waiver of such right or provision."
    )

    pdf.subsection_title("24.6", "Counterparts")
    pdf.body_text(
        "This Contract may be executed in two or more counterparts, each of which shall be deemed "
        "an original, but all of which together shall constitute one and the same instrument. "
        "Execution by electronic signature shall be as valid as original ink signatures."
    )

    pdf.subsection_title("24.7", "Relationship of Parties")
    pdf.body_text(
        "Nothing in this Contract shall be construed to create a partnership, joint venture, agency, "
        "or employment relationship between the Parties. The Supplier is an independent contractor "
        "and shall have no authority to bind the Buyer or to represent itself as the Buyer's agent."
    )

    pdf.subsection_title("24.8", "Survival")
    pdf.body_text(
        "Clauses 9 (Warranty), 11 (Intellectual Property), 12 (Confidentiality), 14 "
        "(Indemnification), 17 (Dispute Resolution), 19 (Data Protection), and 23 "
        "(Anti-Corruption) shall survive the expiration or termination of this Contract."
    )

    # =========================================================================
    # Annexure - Authorized Contacts
    # =========================================================================
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 10, "ANNEXURE I - AUTHORIZED CONTACTS AND ESCALATION MATRIX", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.body_text(
        "The following authorized contacts shall serve as the primary points of contact for the "
        "administration and performance of this Contract:"
    )

    pdf.subsection_title("", "Buyer's Authorized Contacts")
    cw = [40, 50, 45, 40]
    pdf.table_row(["Role", "Name", "Email", "Phone"], cw, bold=True, fill=True)
    pdf.table_row(["Contract Owner", "Sarah Mitchell", "s.mitchell@vialto.com", "+1-212-555-0101"], cw)
    pdf.table_row(["IT Manager", "Rajesh Kumar", "r.kumar@vialto.com", "+1-212-555-0102"], cw)
    pdf.table_row(["Procurement Lead", "Jennifer Adams", "j.adams@vialto.com", "+1-212-555-0103"], cw)
    pdf.table_row(["Finance Contact", "Michael Chen", "m.chen@vialto.com", "+1-212-555-0104"], cw)
    pdf.ln(5)

    pdf.subsection_title("", "Supplier's Authorized Contacts")
    pdf.table_row(["Role", "Name", "Email", "Phone"], cw, bold=True, fill=True)
    pdf.table_row(["Account Manager", "Priya Sharma", "p.sharma@compuserve.in", "+91-124-555-2001"], cw)
    pdf.table_row(["Technical Lead", "Amit Patel", "a.patel@compuserve.in", "+91-124-555-2002"], cw)
    pdf.table_row(["Service Manager", "Deepak Verma", "d.verma@compuserve.in", "+91-124-555-2003"], cw)
    pdf.table_row(["Regional Director", "Vikram Singh", "v.singh@compuserve.in", "+91-124-555-2004"], cw)
    pdf.ln(5)

    pdf.subsection_title("", "Escalation Matrix")
    pdf.body_text(
        "Escalation of unresolved issues shall follow the sequence below. Each level shall have "
        "five (5) business days to resolve the issue before escalation to the next level:"
    )
    ew = [15, 45, 60, 55]
    pdf.table_row(["Level", "Buyer", "Supplier", "Timeframe"], ew, bold=True, fill=True)
    pdf.table_row(["1", "IT Manager", "Account Manager", "5 business days"], ew)
    pdf.table_row(["2", "Procurement Lead", "Service Manager", "5 business days"], ew)
    pdf.table_row(["3", "VP Operations", "Regional Director", "5 business days"], ew)
    pdf.table_row(["4", "General Counsel", "Managing Director", "Per Clause 17"], ew)
    pdf.ln(8)

    # =========================================================================
    # Annexure II - Acceptance Certificate Template
    # =========================================================================
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 10, "ANNEXURE II - ACCEPTANCE CERTIFICATE TEMPLATE", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.body_text("Contract Reference: VP/PROC/2026/LC-001")
    pdf.body_text("Date of Inspection: ___________________")
    pdf.body_text("Inspected By: ________________________")
    pdf.ln(3)

    aw = [10, 35, 35, 35, 30, 30]
    pdf.table_row(["#", "Serial No.", "Model", "OS Activated", "Office Lic.", "Status"], aw, bold=True, fill=True)
    for i in range(1, 15):
        pdf.table_row([str(i), "____________", "____________", "Y / N", "Y / N", "Pass / Fail"], aw)
    pdf.ln(5)

    pdf.body_text("Comments / Deficiencies Noted:")
    pdf.body_text("___________________________________________________________________________")
    pdf.body_text("___________________________________________________________________________")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 6, "ACCEPTANCE DECISION:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "[ ] ACCEPTED - All Goods conform to specifications", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "[ ] CONDITIONALLY ACCEPTED - Minor deficiencies to be rectified by: ________", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "[ ] REJECTED - Material non-conformance (details above)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    pdf.cell(85, 6, "___________________________________")
    pdf.cell(85, 6, "___________________________________")
    pdf.ln(6)
    pdf.cell(85, 6, "Buyer's Representative")
    pdf.cell(85, 6, "Supplier's Representative")
    pdf.ln(6)
    pdf.cell(85, 6, "Date: _____________________________")
    pdf.cell(85, 6, "Date: _____________________________")

    # =========================================================================
    # Signature Page
    # =========================================================================
    pdf.add_page()
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 10, "EXECUTION", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.body_text(
        "IN WITNESS WHEREOF, the Parties hereto have caused this Contract to be executed by their "
        "duly authorized representatives as of the date first written above."
    )

    pdf.ln(10)

    # Buyer signature block
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 7, "FOR AND ON BEHALF OF THE BUYER:", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 7, "Vialto Partners LLC", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(85, 6, "___________________________________")
    pdf.cell(85, 6, "___________________________________")
    pdf.ln(6)
    pdf.cell(85, 6, "Authorized Signatory")
    pdf.cell(85, 6, "Date")
    pdf.ln(6)
    pdf.cell(85, 6, "Name: _____________________________")
    pdf.cell(85, 6, "")
    pdf.ln(6)
    pdf.cell(85, 6, "Title: ______________________________")
    pdf.ln(6)
    pdf.cell(85, 6, "Witness: ___________________________")
    pdf.ln(20)

    # Supplier signature block
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 7, "FOR AND ON BEHALF OF THE SUPPLIER:", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 7, "CompuServe Technologies Private Limited", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(85, 6, "___________________________________")
    pdf.cell(85, 6, "___________________________________")
    pdf.ln(6)
    pdf.cell(85, 6, "Authorized Signatory")
    pdf.cell(85, 6, "Date")
    pdf.ln(6)
    pdf.cell(85, 6, "Name: _____________________________")
    pdf.cell(85, 6, "")
    pdf.ln(6)
    pdf.cell(85, 6, "Title: ______________________________")
    pdf.ln(6)
    pdf.cell(85, 6, "Witness: ___________________________")
    pdf.ln(20)

    # Seal area
    pdf.set_draw_color(150, 150, 150)
    pdf.set_line_width(0.3)
    pdf.rect(65, pdf.get_y(), 80, 30)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.set_y(pdf.get_y() + 12)
    pdf.cell(0, 5, "[Company Seals / Stamps]", align="C")

    # Output
    output_path = "../test-data/Vialto_CompuServe_Laptop_Procurement_Contract_2026.pdf"
    pdf.output(output_path)
    print(f"Contract generated: {output_path}")
    print(f"Pages: {pdf.page_no()}")


if __name__ == "__main__":
    generate()
