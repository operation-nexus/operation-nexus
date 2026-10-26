/**
 * DOM and Canvas creation utilities with graceful headless/node fallback.
 * Guarantees zero runtime crashes across both real browsers and headless test runners.
 */

export function createMockCanvasContext(): CanvasRenderingContext2D {
  return {
    save: () => {},
    restore: () => {},
    scale: () => {},
    translate: () => {},
    rotate: () => {},
    beginPath: () => {},
    moveTo: () => {},
    lineTo: () => {},
    closePath: () => {},
    arc: () => {},
    rect: () => {},
    fillRect: () => {},
    strokeRect: () => {},
    fillText: () => {},
    stroke: () => {},
    fill: () => {},
    createRadialGradient: () => ({ addColorStop: () => {} }),
    setLineDash: () => {},
    strokeStyle: "",
    fillStyle: "",
    lineWidth: 0,
    shadowColor: "",
    shadowBlur: 0,
    globalAlpha: 1,
    font: "",
    textAlign: "",
    imageSmoothingEnabled: true,
  } as unknown as CanvasRenderingContext2D;
}

export function createCanvasElement(
  container: HTMLElement,
  className: string,
): HTMLCanvasElement {
  if (typeof document !== "undefined") {
    const canvas = document.createElement("canvas");
    canvas.className = className;
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.display = "block";
    container.appendChild(canvas);
    return canvas;
  }

  // Headless environment mock canvas
  const canvas = {
    className,
    width: 1280,
    height: 720,
    style: { width: "100%", height: "100%", display: "block" },
    getContext: () => createMockCanvasContext(),
  } as unknown as HTMLCanvasElement;
  container.appendChild(canvas);
  return canvas;
}

export class MockDomElement {
  tagName: string;
  className = "";
  id = "";
  style: Record<string, string> = {};
  parentElement: MockDomElement | null = null;
  children: MockDomElement[] = [];
  private _innerHTML = "";
  private _textContent = "";

  constructor(tagName = "div") {
    this.tagName = tagName.toUpperCase();
  }

  get textContent(): string {
    if (this._textContent) return this._textContent;
    if (this._innerHTML) return this._innerHTML.replace(/<[^>]+>/g, " ").trim();
    return this.children.map((c) => c.textContent).join(" ");
  }

  set textContent(text: string) {
    this._textContent = text;
    this._innerHTML = "";
    this.children = [];
  }

  get innerHTML(): string {
    return this._innerHTML;
  }

  set innerHTML(html: string) {
    this._innerHTML = html;
    this._textContent = "";
    this.children = [];

    // Strip HTML comments (repeat to avoid incomplete multi-character sanitization)
    let cleanHtml = html;
    let previousHtml: string;
    do {
      previousHtml = cleanHtml;
      cleanHtml = cleanHtml.replace(/<!--[\s\S]*?-->/g, "");
    } while (cleanHtml !== previousHtml);

    // Match all HTML opening tags
    const tagRegex = /<([a-zA-Z0-9-]+)([^>]*)>/g;
    const idRegex = /id="([^"]+)"/;
    const classRegex = /class="([^"]+)"/;

    let match: RegExpExecArray | null;
    while ((match = tagRegex.exec(cleanHtml)) !== null) {
      const tag = match[1] ?? "div";
      if (tag.startsWith("/")) continue;
      const attrs = match[2] ?? "";

      const idMatch = idRegex.exec(attrs);
      const classMatch = classRegex.exec(attrs);

      if (idMatch || classMatch) {
        const child = new MockDomElement(tag);
        if (idMatch && idMatch[1]) child.id = idMatch[1];
        if (classMatch && classMatch[1]) child.className = classMatch[1];
        this.appendChild(child);
      }
    }
  }

  appendChild(child: MockDomElement): MockDomElement {
    this.children.push(child);
    child.parentElement = this;
    return child;
  }

  removeChild(child: MockDomElement): MockDomElement {
    const idx = this.children.indexOf(child);
    if (idx !== -1) {
      this.children.splice(idx, 1);
    }
    child.parentElement = null;
    return child;
  }

  replaceChildren(...nodes: MockDomElement[]): void {
    for (const child of this.children) {
      child.parentElement = null;
    }
    this.children = [];
    this._innerHTML = "";
    this._textContent = "";
    for (const node of nodes) {
      this.appendChild(node);
    }
  }

  querySelector(selector: string): MockDomElement | null {
    const results = this.querySelectorAll(selector);
    return results[0] ?? null;
  }

  querySelectorAll(selector: string): MockDomElement[] {
    const results: MockDomElement[] = [];
    const match = (el: MockDomElement) => {
      if (selector.startsWith("#") && el.id === selector.slice(1)) {
        results.push(el);
      } else if (
        selector.startsWith(".") &&
        el.className.split(/\s+/).filter(Boolean).includes(selector.slice(1))
      ) {
        results.push(el);
      } else if (el.tagName.toLowerCase() === selector.toLowerCase()) {
        results.push(el);
      }
      for (const child of el.children) {
        match(child);
      }
    };
    for (const child of this.children) {
      match(child);
    }
    return results;
  }
}

export function createElement(
  tagName: string,
  className?: string,
): HTMLElement {
  if (typeof document !== "undefined") {
    const el = document.createElement(tagName);
    if (className) el.className = className;
    return el;
  }
  const mock = new MockDomElement(tagName);
  if (className) mock.className = className;
  return mock as unknown as HTMLElement;
}
