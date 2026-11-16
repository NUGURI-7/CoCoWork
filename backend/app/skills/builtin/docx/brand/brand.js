// CoCoWork 品牌 Word 模块：页眉（Logo + 公司名 + 品牌色横线）、页脚（资料密级 + 页码）、
// 中文字体与标题样式、封面、列表与表格。新建 Word 文档一律通过 createDocument() 生成。
//
//   const brand = require("<本 skill 目录>/brand/brand.js");
//   const doc = brand.createDocument({ title, cover, classification, children: [...] });
//   await brand.save(doc, "<交付区>/方案.docx");
const fs = require("fs");
const path = require("path");
const {
	AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel, ImageRun, LevelFormat,
	Packer, PageBreak, PageNumber, Paragraph, ShadingType, Table, TableCell, TableRow, TabStopType,
	TextRun, WidthType,
} = require("docx");

const BRAND = {
	company: "CoCoWork",
	color: "2F6B53",
	colorDeep: "163828",
	colorLight: "E3EEE8",
	colorTint: "F1F6F3",
	line: "DCE7E1",
	accent: "C9A86A",
	textMuted: "5F6B65",
	latinFont: "Arial",
	headingFont: "微软雅黑",
	bodyFont: "宋体",
};

// A4，上下 1440、左右 1300 DXA（1440 = 1 英寸）
const PAGE = { width: 11906, height: 16838, marginX: 1300, marginY: 1440 };
const CONTENT_WIDTH = PAGE.width - PAGE.marginX * 2;

const LOGO = fs.readFileSync(path.join(__dirname, "logo.png"));

const font = (eastAsia) => ({ ascii: BRAND.latinFont, hAnsi: BRAND.latinFont, eastAsia, cs: BRAND.latinFont });

function headingStyle(size, before, after) {
	return {
		run: { font: font(BRAND.headingFont), size, bold: true, color: BRAND.color },
		paragraph: { spacing: { before, after }, keepNext: true, keepLines: true },
	};
}

const STYLES = {
	default: {
		document: { run: { font: font(BRAND.bodyFont), size: 22 }, paragraph: { spacing: { line: 360 } } },
		title: headingStyle(44, 0, 240),
		heading1: headingStyle(32, 480, 200),
		heading2: headingStyle(28, 240, 120),
		heading3: headingStyle(24, 200, 100),
	},
};

const NUMBERING = {
	config: [
		{
			reference: "brand-bullets",
			levels: [0, 1, 2].map((level) => ({
				level,
				format: LevelFormat.BULLET,
				text: ["●", "○", "■"][level],
				alignment: AlignmentType.LEFT,
				style: { paragraph: { indent: { left: 420 * (level + 1), hanging: 280 } } },
			})),
		},
		{
			reference: "brand-numbers",
			levels: [{
				level: 0,
				format: LevelFormat.DECIMAL,
				text: "%1.",
				alignment: AlignmentType.LEFT,
				style: { paragraph: { indent: { left: 420, hanging: 300 } } },
			}],
		},
	],
};

function brandHeader(title) {
	return new Header({
		children: [new Paragraph({
			tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_WIDTH }],
			children: [
				new ImageRun({ type: "png", data: LOGO, transformation: { width: 16, height: 16 } }),
				new TextRun({ text: `  ${BRAND.company}`, bold: true, color: BRAND.color, size: 18, font: font(BRAND.headingFont) }),
				new TextRun({ text: `\t${title}`, color: BRAND.textMuted, size: 16, font: font(BRAND.headingFont) }),
			],
			border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BRAND.line, space: 6 } },
		})],
	});
}

function brandFooter(classification) {
	return new Footer({
		children: [new Paragraph({
			tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_WIDTH }],
			children: [
				new TextRun({ text: classification, size: 18, color: BRAND.textMuted }),
				new TextRun({ children: ["\t第 ", PageNumber.CURRENT, " 页 / 共 ", PageNumber.TOTAL_PAGES, " 页"], size: 18, color: BRAND.textMuted }),
			],
		})],
	});
}

// ── 图片尺寸（PNG / JPEG 文件头），配图按原比例缩放到版心宽度 ──
function imageInfo(file) {
	const buf = fs.readFileSync(file);
	if (buf.readUInt32BE(0) === 0x89504e47) return { buf, type: "png", width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
	if (buf[0] === 0xff && buf[1] === 0xd8) {
		let i = 2;
		while (i < buf.length) {
			const marker = buf[i + 1];
			const len = buf.readUInt16BE(i + 2);
			if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) {
				return { buf, type: "jpg", width: buf.readUInt16BE(i + 7), height: buf.readUInt16BE(i + 5) };
			}
			i += 2 + len;
		}
	}
	throw new Error(`${file} 不是 PNG / JPEG 图片`);
}

const CONTENT_PX = Math.round((CONTENT_WIDTH / 1440) * 96); // 版心宽度（像素）
const NO_BORDER = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const NO_BORDERS = { top: NO_BORDER, bottom: NO_BORDER, left: NO_BORDER, right: NO_BORDER, insideHorizontal: NO_BORDER, insideVertical: NO_BORDER };

// 金色短横：封面标题下的点缀（与 PPT 封面一致）
function accentBar() {
	return new Table({
		width: { size: 720, type: WidthType.DXA },
		columnWidths: [720],
		borders: NO_BORDERS,
		rows: [new TableRow({
			height: { value: 50, rule: "exact" },
			children: [new TableCell({ width: { size: 720, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, color: "auto", fill: BRAND.accent }, margins: { top: 0, bottom: 0, left: 0, right: 0 }, children: [new Paragraph({ spacing: { before: 0, after: 0, line: 40, lineRule: "exact" }, children: [new TextRun({ text: "", size: 2 })] })] })],
		})],
	});
}

/**
 * 封面：左对齐版式，与 PPT 封面一致。image 给 generate_image 生成的图片路径时，标题上方放一张通栏配图。
 * kicker 是标题上方的英文小标签，如 "PRODUCT PROPOSAL"。
 */
function coverPage({ title, subtitle = "", kicker = "", image = "", date = "", issuer = BRAND.company, classification = "" }) {
	const spacer = (before) => new Paragraph({ spacing: { before } });
	const children = [
		new Paragraph({
			children: [
				new ImageRun({ type: "png", data: LOGO, transformation: { width: 28, height: 28 } }),
				new TextRun({ text: `  ${BRAND.company}`, bold: true, color: BRAND.color, size: 28, font: font(BRAND.headingFont) }),
			],
		}),
	];
	if (image) {
		const info = imageInfo(image);
		children.push(
			spacer(480),
			new Paragraph({ children: [new ImageRun({ type: info.type, data: info.buf, transformation: { width: CONTENT_PX, height: Math.round((CONTENT_PX * info.height) / info.width) } })] }),
			spacer(360),
		);
	} else {
		children.push(spacer(3600));
	}
	if (kicker) {
		children.push(new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: kicker, bold: true, color: BRAND.accent, size: 20, characterSpacing: 60, font: font(BRAND.headingFont) })] }));
	}
	children.push(
		new Paragraph({ spacing: { after: 240 }, children: [new TextRun({ text: title, bold: true, color: BRAND.colorDeep, size: 60, font: font(BRAND.headingFont) })] }),
		accentBar(),
	);
	if (subtitle) {
		children.push(new Paragraph({ spacing: { before: 240 }, children: [new TextRun({ text: subtitle, size: 28, color: BRAND.textMuted, font: font(BRAND.headingFont) })] }));
	}
	children.push(spacer(image ? 1800 : 4200));
	const meta = [[issuer, { bold: true, color: BRAND.color, size: 22 }], [date, { color: BRAND.textMuted, size: 20 }], [classification, { color: BRAND.textMuted, size: 20 }]];
	for (const [text, opts] of meta) {
		if (text) children.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text, font: font(BRAND.headingFont), ...opts })] }));
	}
	children.push(new Paragraph({ children: [new PageBreak()] }));
	return children;
}

/** 提示框：浅绿底，标题加粗品牌色，适合放结论、要点摘要。 */
function callout(title, text) {
	return new Table({
		width: { size: CONTENT_WIDTH, type: WidthType.DXA },
		columnWidths: [CONTENT_WIDTH],
		borders: NO_BORDERS,
		rows: [new TableRow({
			children: [new TableCell({
				width: { size: CONTENT_WIDTH, type: WidthType.DXA },
				shading: { type: ShadingType.CLEAR, color: "auto", fill: BRAND.colorTint },
				margins: { top: 200, bottom: 200, left: 280, right: 280 },
				children: [
					new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: title, bold: true, color: BRAND.color, size: 24, font: font(BRAND.headingFont) })] }),
					new Paragraph({ children: [new TextRun({ text, size: 21 })] }),
				],
			})],
		})],
	});
}

/** 数据卡片行：2–4 个大数字 + 说明，第一个用品牌色底（与 PPT 数据页一致）。items: [{ value: "3 分钟", label: "产出方案初稿" }] */
function statRow(items) {
	if (!Array.isArray(items) || items.length < 2 || items.length > 4) throw new Error(`statRow 需要 2–4 项，现在是 ${items && items.length} 项`);
	const gap = 160;
	const w = Math.floor((CONTENT_WIDTH - gap * (items.length - 1)) / items.length);
	const widths = items.flatMap((_, i) => (i ? [gap, w] : [w]));
	const cardBorder = { style: BorderStyle.SINGLE, size: 4, color: BRAND.line };
	const cells = [];
	items.forEach((it, i) => {
		if (i) cells.push(new TableCell({ width: { size: gap, type: WidthType.DXA }, borders: { top: NO_BORDER, bottom: NO_BORDER, left: NO_BORDER, right: NO_BORDER }, children: [new Paragraph({})] }));
		const hot = i === 0;
		cells.push(new TableCell({
			width: { size: w, type: WidthType.DXA },
			borders: hot ? { top: NO_BORDER, bottom: NO_BORDER, left: NO_BORDER, right: NO_BORDER } : { top: cardBorder, bottom: cardBorder, left: cardBorder, right: cardBorder },
			shading: hot ? { type: ShadingType.CLEAR, color: "auto", fill: BRAND.color } : undefined,
			margins: { top: 240, bottom: 240, left: 240, right: 200 },
			children: [
				new Paragraph({ children: [new TextRun({ text: it.value, bold: true, size: 44, color: hot ? "FFFFFF" : BRAND.color, font: font(BRAND.headingFont) })] }),
				new Paragraph({ spacing: { before: 80 }, children: [new TextRun({ text: it.label, size: 20, color: hot ? BRAND.colorLight : BRAND.textMuted, font: font(BRAND.headingFont) })] }),
			],
		}));
	});
	return new Table({ width: { size: CONTENT_WIDTH, type: WidthType.DXA }, columnWidths: widths, borders: NO_BORDERS, rows: [new TableRow({ children: cells })] });
}

/** 配图：按原比例缩放到版心宽度（widthRatio 可缩小，如 0.7），下方居中小字图注。 */
function figure(file, caption = "", { widthRatio = 1 } = {}) {
	const info = imageInfo(file);
	const width = Math.round(CONTENT_PX * widthRatio);
	const out = [new Paragraph({
		alignment: AlignmentType.CENTER,
		spacing: { before: 120, after: caption ? 60 : 200 },
		children: [new ImageRun({ type: info.type, data: info.buf, transformation: { width, height: Math.round((width * info.height) / info.width) } })],
	})];
	if (caption) out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: caption, size: 18, color: BRAND.textMuted })] }));
	return out;
}

/** 标题：level 1–3，对应 Heading1–3（进目录、带品牌色）。 */
function heading(text, level = 1) {
	const levels = { 1: HeadingLevel.HEADING_1, 2: HeadingLevel.HEADING_2, 3: HeadingLevel.HEADING_3 };
	return new Paragraph({ heading: levels[level] || HeadingLevel.HEADING_1, text });
}

/** 正文段落：text 为字符串，或 TextRun 选项数组（如 [{ text: "要点：", bold: true }, { text: "说明" }]）。 */
function paragraph(text, options = {}) {
	const runs = Array.isArray(text) ? text.map((r) => new TextRun(r)) : [new TextRun(text)];
	return new Paragraph({ spacing: { after: 120 }, indent: { firstLine: options.indent === false ? 0 : 440 }, ...options, children: runs });
}

/** 项目符号列表；numbered 为 true 时改为 1. 2. 3. 编号。 */
function bullets(items, { numbered = false } = {}) {
	const reference = numbered ? "brand-numbers" : "brand-bullets";
	return items.map((item) => new Paragraph({
		numbering: { reference, level: 0 },
		spacing: { after: 60 },
		children: Array.isArray(item) ? item.map((r) => new TextRun(r)) : [new TextRun(item)],
	}));
}

/** 表格：rows[0] 为表头（品牌色底、白字），columnWidths 为各列 DXA 宽度，缺省则均分整行。 */
function table(rows, columnWidths) {
	const cols = rows[0].length;
	const widths = columnWidths || Array(cols).fill(Math.floor(CONTENT_WIDTH / cols));
	const total = widths.reduce((a, b) => a + b, 0);
	const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: BRAND.line };
	const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
	return new Table({
		width: { size: total, type: WidthType.DXA },
		columnWidths: widths,
		rows: rows.map((row, r) => new TableRow({
			tableHeader: r === 0,
			children: row.map((value, c) => new TableCell({
				width: { size: widths[c], type: WidthType.DXA },
				borders,
				margins: { top: 80, bottom: 80, left: 120, right: 120 },
				shading: r === 0
					? { type: ShadingType.CLEAR, color: "auto", fill: BRAND.color }
					: r % 2 === 0 ? { type: ShadingType.CLEAR, color: "auto", fill: BRAND.colorTint } : undefined,
				children: [new Paragraph({
					children: [new TextRun({ text: String(value), bold: r === 0, color: r === 0 ? "FFFFFF" : undefined, size: 20 })],
				})],
			})),
		})),
	});
}

/**
 * 生成带品牌页眉页脚的文档。
 * children 可混放段落、表格和 bullets() 返回的数组。
 * cover 给了就在第一页生成封面（封面页不带页眉页脚）；classification 显示在页脚左侧，如「对外资料」「内部资料」。
 */
function createDocument({ title, children, cover, classification = "对外资料", author = BRAND.company }) {
	// 允许直接放 bullets() 这类返回数组的结果，统一拍平
	const flat = children.flat(Infinity);
	const body = cover ? [...coverPage({ title, classification, ...cover }), ...flat] : flat;
	const empty = () => [new Paragraph({})];
	return new Document({
		title,
		creator: author,
		lastModifiedBy: author,
		styles: STYLES,
		numbering: NUMBERING,
		features: { updateFields: true },
		sections: [{
			properties: {
				titlePage: Boolean(cover),
				page: {
					size: { width: PAGE.width, height: PAGE.height },
					margin: { top: PAGE.marginY, bottom: PAGE.marginY, left: PAGE.marginX, right: PAGE.marginX },
				},
			},
			headers: { default: brandHeader(title), ...(cover ? { first: new Header({ children: empty() }) } : {}) },
			footers: { default: brandFooter(classification), ...(cover ? { first: new Footer({ children: empty() }) } : {}) },
			children: body,
		}],
	});
}

/** 写文件：输出 .docx，目录不存在时自动创建。 */
async function save(doc, filePath) {
	fs.mkdirSync(path.dirname(filePath), { recursive: true });
	fs.writeFileSync(filePath, await Packer.toBuffer(doc));
	return filePath;
}

module.exports = { BRAND, CONTENT_WIDTH, createDocument, coverPage, heading, paragraph, bullets, table, callout, statRow, figure, save };
