const unitScaleFor = (unit) => (unit === "inch" ? 25.4 : 1);

function parseToolDiameters(text, unitScale) {
    const tools = new Map();
    for (const line of text.split(/\r?\n/)) {
        const match = line.trim().match(/^T(\d+).*?C([+-]?(?:\d+\.?\d*|\.\d+))/i);
        if (match) tools.set(match[1], Number(match[2]) * unitScale);
    }
    return tools;
}

function parseExcellonFile(file) {
    const text = file.content.replace(/^\uFEFF/, "");
    const headerUnit = /\bINCH\b|\bG20\b/i.test(text) ? "inch" : "mm";
    let unitScale = unitScaleFor(headerUnit);
    const mode = text.match(/(?:METRIC|INCH)\s*,\s*(LZ|TZ)/i);
    let zeroSuppression = mode?.[1]?.toUpperCase() || "LZ";
    const formatMatch = text.match(/^\s*;\s*(?:FILE_FORMAT|FORMAT)\s*=\s*(\d+)\s*:\s*(\d+)/im);
    let integerDigits = formatMatch ? Number(formatMatch[1]) : (headerUnit === "mm" ? 3 : 2);
    let decimalDigits = formatMatch ? Number(formatMatch[2]) : (headerUnit === "mm" ? 3 : 4);
    let incremental = false;
    let currentTool = null;
    let x = null;
    let y = null;
    const tools = parseToolDiameters(text, unitScale);
    const hits = [];

    const coordinate = (raw) => {
        if (raw.includes(".")) return Number(raw) * unitScale;
        const sign = raw.startsWith("-") ? -1 : 1;
        const digits = raw.replace(/^[+-]/, "");
        const width = integerDigits + decimalDigits;
        const padded = zeroSuppression === "TZ" ? digits.padEnd(width, "0") : digits.padStart(width, "0");
        return sign * Number(padded) / (10 ** decimalDigits) * unitScale;
    };

    for (const [index, rawLine] of text.split(/\r?\n/).entries()) {
        let line = rawLine.replace(/\([^)]*\)/g, "").trim().toUpperCase().replace(/\s+/g, "");
        if (!line || line.startsWith(";") || line === "%") continue;
        if (/^(M30|M00|M02)$/.test(line)) continue;
        if (/G85/.test(line)) {
            throw new Error(`${file.name}, line ${index + 1}: routed slots (G85) are not supported by the drill G-code exporter.`);
        }
        if (/^G90$/.test(line)) { incremental = false; continue; }
        if (/^G91$/.test(line)) { incremental = true; continue; }
        if (/^G20$/.test(line)) { unitScale = 25.4; continue; }
        if (/^G21$/.test(line)) { unitScale = 1; continue; }
        const unitMatch = line.match(/^(METRIC|INCH)(?:,(LZ|TZ))?/);
        if (unitMatch) {
            unitScale = unitScaleFor(unitMatch[1].toLowerCase());
            if (unitMatch[2]) zeroSuppression = unitMatch[2];
            continue;
        }
        const format = line.match(/^FILE_FORMAT=(\d+):(\d+)/);
        if (format) { integerDigits = Number(format[1]); decimalDigits = Number(format[2]); continue; }

        const definition = line.match(/^T(\d+).*?C([+-]?(?:\d+\.?\d*|\.\d+))/);
        if (definition) {
            tools.set(definition[1], Number(definition[2]) * unitScale);
            continue;
        }
        const selection = line.match(/^T(\d+)$/);
        if (selection) { currentTool = selection[1]; continue; }

        const fields = [...line.matchAll(/([XY])([+-]?(?:\d+\.?\d*|\.\d+))/g)];
        if (!fields.length) continue;
        if (!currentTool) throw new Error(`${file.name}, line ${index + 1}: coordinate found before a drill tool was selected.`);
        let nextX = null;
        let nextY = null;
        for (const field of fields) {
            const value = coordinate(field[2]);
            if (field[1] === "X") nextX = value;
            else nextY = value;
        }
        if (incremental) {
            x = (x || 0) + (nextX || 0);
            y = (y || 0) + (nextY || 0);
        } else {
            if (nextX !== null) x = nextX;
            if (nextY !== null) y = nextY;
        }
        if (x === null || y === null) throw new Error(`${file.name}, line ${index + 1}: drill hit is missing X or Y.`);
        const diameter = tools.get(currentTool);
        if (!Number.isFinite(diameter) || diameter <= 0) throw new Error(`${file.name}: drill T${currentTool} has no valid diameter definition.`);
        hits.push({ x, y, diameter, toolNumber: currentTool });
    }
    return hits;
}

export function generateDrillGcode(drillFiles, outlinePath, settings) {
    if (!drillFiles?.length) throw new Error("No drill files were loaded. Include the KiCad Excellon .drl file.");
    if (!outlinePath) throw new Error("No board outline was found. Include the Edge.Cuts Gerber when uploading the board files.");
    const bounds = outlinePath.getBBox();
    if (![bounds.x, bounds.y, bounds.width, bounds.height].every(Number.isFinite) || bounds.width <= 0 || bounds.height <= 0) {
        throw new Error("Could not measure the board outline. Check that the Edge.Cuts layer contains a closed outline.");
    }

    const allHits = drillFiles.flatMap(parseExcellonFile);
    const unique = new Map();
    for (const hit of allHits) {
        const key = `${hit.diameter.toFixed(5)}:${hit.x.toFixed(5)}:${hit.y.toFixed(5)}`;
        if (!unique.has(key)) unique.set(key, hit);
    }
    const grouped = new Map();
    for (const hit of unique.values()) {
        const key = hit.diameter.toFixed(5);
        if (!grouped.has(key)) grouped.set(key, { diameter: hit.diameter, hits: [] });
        grouped.get(key).hits.push(hit);
    }
    const groups = [...grouped.values()].sort((a, b) => a.diameter - b.diameter);
    if (!groups.length) throw new Error("No drill hits were found in the loaded Excellon files.");

    const minX = bounds.x;
    const minY = bounds.y;
    const maxX = bounds.x + bounds.width;
    const tolerance = Math.max(bounds.width, bounds.height) * 0.01 + 0.1;
    const outside = [...unique.values()].filter((hit) => hit.x < minX - tolerance || hit.x > maxX + tolerance || hit.y < minY - tolerance || hit.y > maxY + tolerance);
    if (outside.length) {
        throw new Error(`Drill coordinates do not align with the board outline (${outside.length} hit(s) fall outside its bounds). Ensure the drill and Gerber files use the same origin and units.`);
    }

    const depth = Number(settings.depth);
    const safeZ = Number(settings.safeZ);
    const toolChangeZ = Number(settings.toolChangeZ);
    const plunge = Number(settings.plunge);
    const spindle = Number(settings.spindle);
    const dwell = Number(settings.dwell);
    if (![depth, safeZ, toolChangeZ, plunge, spindle, dwell].every(Number.isFinite) || depth >= 0 || safeZ <= 0 || toolChangeZ < safeZ || plunge <= 0 || spindle < 0 || dwell < 0) {
        throw new Error("Check the G-code settings. Depth must be negative; safe Z, feed, and tool-change heights must be valid.");
    }

    const fmt = (value) => (Object.is(value, -0) ? 0 : value).toFixed(3);
    const lines = [
        "(Gerber2PNG Local - drill G-code)",
        "(Top-side orientation; board outline lower-left is X0 Y0)",
        `(Board bounds: ${fmt(bounds.width)} x ${fmt(bounds.height)} mm; ${unique.size} unique holes)`,
        "G21",
        "G90",
        "G94",
        "G17",
        "M5",
        `G0 Z${fmt(safeZ)}`,
    ];
    groups.forEach((group, index) => {
        lines.push("M5", `G0 Z${fmt(toolChangeZ)}`);
        lines.push(`(Install drill ${index + 1}/${groups.length}: ${group.diameter.toFixed(3)} mm, ${group.hits.length} holes)`);
        lines.push("M0");
        if (spindle > 0) lines.push(`M3 S${Math.round(spindle)}`, `G4 P${fmt(dwell)}`);
        group.hits.sort((a, b) => a.y - b.y || a.x - b.x).forEach((hit) => {
            const x = hit.x - minX;
            const y = hit.y - minY;
            lines.push(`G0 X${fmt(x)} Y${fmt(y)}`, `G1 Z${fmt(depth)} F${fmt(plunge)}`, `G0 Z${fmt(safeZ)}`);
        });
    });
    lines.push("M5", `G0 Z${fmt(toolChangeZ)}`, "M30", "");
    return { gcode: lines.join("\n"), holeCount: unique.size, toolCount: groups.length };
}
