const CSS_PX_TO_MM = 25.4 / 96;
const MAX_SEGMENT_MM = 0.08;
const MAX_POINTS_PER_CONTOUR = 12000;

export function createStencilDxf(svgRoot, side, boardSize = {}) {
  if (!svgRoot) throw new Error("Load a Gerber set before generating a stencil DXF.");

  const workingRoot = svgRoot.cloneNode(true);
  const sandbox = document.createElement("div");
  sandbox.setAttribute("aria-hidden", "true");
  Object.assign(sandbox.style, {
    position: "fixed",
    left: "-10000px",
    top: "0",
    visibility: "hidden",
    pointerEvents: "none",
    overflow: "visible",
  });
  workingRoot.style.display = "block";
  workingRoot.style.visibility = "visible";
  sandbox.appendChild(workingRoot);
  document.body.appendChild(sandbox);

  try {
    const groupSelector = 'g[id*="' + side + '_solderpaste"]';
    const pasteGroups = Array.from(workingRoot.querySelectorAll(groupSelector));
    pasteGroups.forEach(forceVisible);
    const pastePaths = pasteGroups.flatMap((group) => expandUseGeometry(group, workingRoot));
    const outlinePath = workingRoot.querySelector("#drillMask path");
    if (outlinePath) forceVisible(outlinePath);
    if (!pastePaths.length) {
      throw new Error("No " + side + " solder-paste apertures were found in the loaded Gerbers.");
    }
    if (!outlinePath) {
      throw new Error("No board outline was found. Include the Edge.Cuts Gerber.");
    }

    const outlineContours = pathContours(outlinePath, workingRoot);
    const apertureContours = pastePaths.flatMap((path) =>
      pathContours(path, workingRoot)
    );
    const outlinePoints = outlineContours.flatMap((contour) => contour.points);
    if (!outlinePoints.length || !apertureContours.length) {
      throw new Error("The selected paste layer or board outline contains no exportable paths.");
    }

    const bounds = getBounds(outlinePoints);
    const width = bounds.maxX - bounds.minX;
    const height = bounds.maxY - bounds.minY;
    if (!(width > 0) || !(height > 0)) {
      throw new Error("The board outline has no measurable width or height.");
    }

    const scaleX = (Number(boardSize.width) > 0 ? Number(boardSize.width) : width) / width;
    const scaleY = (Number(boardSize.height) > 0 ? Number(boardSize.height) : height) / height;
    const toDxfContour = (contour) => ({
      closed: contour.closed,
      points: contour.points.map(({ x, y }) => [
        (x - bounds.minX) * scaleX,
        (bounds.maxY - y) * scaleY,
      ]),
    });

    const edge = outlineContours.map(toDxfContour);
    const apertures = apertureContours.map((contour) => ({
      ...toDxfContour(contour),
      closed: true,
    }));

    return serializeDxf({ side, edge, apertures });
  } finally {
    sandbox.remove();
  }
}

function expandUseGeometry(group, svgRoot) {
  const svgNamespace = "http://www.w3.org/2000/svg";
  const useElements = Array.from(group.querySelectorAll("use"));

  useElements.forEach((useElement) => {
    const href = useElement.getAttribute("href") ||
      useElement.getAttributeNS("http://www.w3.org/1999/xlink", "href");
    if (!href || !href.startsWith("#")) return;

    const referencedId = href.slice(1);
    const referencedElement = Array.from(svgRoot.querySelectorAll("[id]"))
      .find((element) => element.id === referencedId);
    if (!referencedElement) return;

    const instance = document.createElementNS(svgNamespace, "g");
    const transforms = [];
    if (useElement.hasAttribute("transform")) {
      transforms.push(useElement.getAttribute("transform"));
    }
    const x = Number(useElement.getAttribute("x") || 0);
    const y = Number(useElement.getAttribute("y") || 0);
    if (x || y) transforms.push("translate(" + x + " " + y + ")");
    if (transforms.length) instance.setAttribute("transform", transforms.join(" "));

    const clone = referencedElement.cloneNode(true);
    clone.removeAttribute("id");
    instance.appendChild(clone);
    useElement.parentNode.appendChild(instance);
  });

  return Array.from(group.querySelectorAll("path"));
}

function forceVisible(element) {
  let current = element;
  while (current && current.tagName?.toLowerCase() !== "svg") {
    current.style.display = "block";
    current.style.visibility = "visible";
    current = current.parentElement;
  }
}

function pathContours(path, svgRoot) {
  const originalD = path.getAttribute("d") || "";
  const subpaths = splitSubpaths(originalD);
  const contours = [];
  const rootScreenMatrix = svgRoot.getScreenCTM();
  if (!rootScreenMatrix) {
    throw new Error("Could not read the Gerber SVG coordinate transform.");
  }
  const rootInverse = rootScreenMatrix.inverse();

  try {
    for (const subpath of subpaths) {
      path.setAttribute("d", subpath.d);
      const length = path.getTotalLength();
      if (!Number.isFinite(length) || length <= 0) continue;

      const pathMatrix = path.getScreenCTM();
      if (!pathMatrix) continue;
      const mmPerUnit = localUnitToMm(pathMatrix);
      const step = MAX_SEGMENT_MM / mmPerUnit;
      const count = Math.min(
        MAX_POINTS_PER_CONTOUR,
        Math.max(4, Math.ceil(length / step))
      );
      const points = [];
      const sampleCount = subpath.closed ? count : count + 1;

      for (let index = 0; index < sampleCount; index += 1) {
        const localPoint = path.getPointAtLength((length * index) / count);
        const screenPoint = new DOMPoint(localPoint.x, localPoint.y).matrixTransform(pathMatrix);
        const rootPoint = screenPoint.matrixTransform(rootInverse);
        points.push({
          x: rootPoint.x * CSS_PX_TO_MM,
          y: rootPoint.y * CSS_PX_TO_MM,
        });
      }

      if (points.length >= 3) {
        contours.push({ points, closed: subpath.closed });
      }
    }
  } finally {
    path.setAttribute("d", originalD);
  }

  return contours;
}

function localUnitToMm(matrix) {
  const xScale = Math.hypot(matrix.a, matrix.b);
  const yScale = Math.hypot(matrix.c, matrix.d);
  const mmPerUnit = Math.max(xScale, yScale) * CSS_PX_TO_MM;
  return mmPerUnit > 0 ? mmPerUnit : CSS_PX_TO_MM;
}

function splitSubpaths(pathData) {
  const tokens = pathData.match(/[a-df-zA-DF-Z]|[-+]?(?:\d*\.?\d+)(?:[eE][-+]?\d+)?/g) || [];
  const subpaths = [];
  let current = [];

  tokens.forEach((token) => {
    if (/^[mM]$/.test(token) && current.length) {
      subpaths.push(makeSubpath(current));
      current = [];
    }
    current.push(token);
  });

  if (current.length) subpaths.push(makeSubpath(current));
  return subpaths;
}

function makeSubpath(tokens) {
  return {
    d: tokens.join(" "),
    closed: tokens.some((token) => /^[zZ]$/.test(token)),
  };
}

function getBounds(points) {
  return points.reduce(
    (bounds, point) => ({
      minX: Math.min(bounds.minX, point.x),
      minY: Math.min(bounds.minY, point.y),
      maxX: Math.max(bounds.maxX, point.x),
      maxY: Math.max(bounds.maxY, point.y),
    }),
    { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity }
  );
}

function serializeDxf({ edge, apertures }) {
  const lines = [
    "0", "SECTION", "2", "HEADER",
    "9", "$ACADVER", "1", "AC1015",
    "9", "$INSUNITS", "70", "4",
    "9", "$MEASUREMENT", "70", "1",
    "0", "ENDSEC",
    "0", "SECTION", "2", "TABLES",
    "0", "TABLE", "2", "LAYER", "70", "2",
    "0", "LAYER", "2", "BOARD_EDGE", "70", "0", "62", "7", "6", "CONTINUOUS",
    "0", "LAYER", "2", "STENCIL_APERTURES", "70", "0", "62", "1", "6", "CONTINUOUS",
    "0", "ENDTAB",
    "0", "ENDSEC",
    "0", "SECTION", "2", "ENTITIES",
  ];

  edge.forEach((contour) => appendPolyline(lines, "BOARD_EDGE", contour));
  apertures.forEach((contour) => appendPolyline(lines, "STENCIL_APERTURES", contour));

  lines.push("0", "ENDSEC", "0", "EOF");
  return lines.join("\r\n");
}

function appendPolyline(lines, layer, contour) {
  const points = removeDuplicatePoints(contour.points);
  if (points.length < 3) return;

  lines.push(
    "0", "LWPOLYLINE",
    "100", "AcDbEntity",
    "8", layer,
    "100", "AcDbPolyline",
    "90", String(points.length),
    "70", contour.closed ? "1" : "0"
  );
  points.forEach(([x, y]) => {
    lines.push("10", formatNumber(x), "20", formatNumber(y));
  });
}

function removeDuplicatePoints(points) {
  const result = [];
  points.forEach(([x, y]) => {
    const previous = result[result.length - 1];
    if (!previous || Math.hypot(x - previous[0], y - previous[1]) > 0.00001) {
      result.push([x, y]);
    }
  });
  if (
    result.length > 2 &&
    Math.hypot(
      result[0][0] - result[result.length - 1][0],
      result[0][1] - result[result.length - 1][1]
    ) < 0.00001
  ) {
    result.pop();
  }
  return result;
}

function formatNumber(value) {
  return Number(value.toFixed(5)).toString();
}
