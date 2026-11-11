import { app } from "../../scripts/app.js";

const NODE = "PxFloatRadioSwitch";
const MAX = 20;
const RW = 26;      // Breite des Radio-Bereichs rechts
const MARGIN = 15;  // Standard-Rand der Widgets

function setHidden(w, hide) {
  if (!w) return;
  if (hide) {
    if (!w._px) w._px = { type: w.type, computeSize: w.computeSize, own: Object.prototype.hasOwnProperty.call(w, "computeSize") };
    w.type = "converted-widget";
    w.hidden = true;
    w.computeSize = () => [0, -4];
  } else if (w._px) {
    w.type = w._px.type;
    if (w._px.own) w.computeSize = w._px.computeSize;
    else delete w.computeSize;
    w.hidden = false;
    delete w._px;
  }
}

function setSlotHidden(node, name, hide) {
  const idx = (node.inputs || []).findIndex((i) => i.name === name);
  if (idx < 0) return;
  const slot = node.inputs[idx];
  if (hide && slot.link != null) node.disconnectInput(idx);
  slot.hidden = hide;
}

app.registerExtension({
  name: "PxRsz.FloatRadioSwitch",
  nodeCreated(node) {
    if (node.comfyClass !== NODE) return;
    const get = (n) => node.widgets.find((w) => w.name === n);
    const countW = get("inputs");
    const selW = get("selected");
    const rows = [];
    for (let i = 1; i <= MAX; i++) rows.push(get("value_" + i));

    const drawRadio = (ctx, w, i, width, y, h) => {
      const cx = width - MARGIN - RW / 2;
      const cy = y + h / 2;
      const active = Number(selW.value) === i;
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, 6, 0, Math.PI * 2);
      ctx.strokeStyle = active ? "#6fd36f" : "#999";
      ctx.lineWidth = 1.5;
      ctx.stroke();
      if (active) {
        ctx.beginPath();
        ctx.arc(cx, cy, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = "#6fd36f";
        ctx.fill();
      }
      ctx.restore();
    };

    rows.forEach((w, k) => {
      if (!w) return;
      const i = k + 1;
      if (typeof w.drawWidget === "function") {
        const o = w.drawWidget;
        w.drawWidget = function (ctx, opts) {
          o.call(this, ctx, { ...opts, width: opts.width - RW });
          drawRadio(ctx, w, i, opts.width, this.y, this.height ?? LiteGraph.NODE_WIDGET_HEIGHT);
        };
      } else {
        const o = w.draw;
        w.draw = function (ctx, n, width, y, h) {
          if (o) o.call(this, ctx, n, width - RW, y, h);
          drawRadio(ctx, w, i, width, y, h ?? LiteGraph.NODE_WIDGET_HEIGHT);
        };
      }
    });

    const prevDown = node.onMouseDown;
    node.onMouseDown = function (e, pos, canvas) {
      const count = parseInt(countW.value);
      if (pos[0] >= this.size[0] - MARGIN - RW - 2) {
        for (let i = 1; i <= count; i++) {
          const w = rows[i - 1];
          const y = w.last_y ?? w.y;
          const h = w.height ?? LiteGraph.NODE_WIDGET_HEIGHT;
          if (y != null && pos[1] >= y && pos[1] <= y + h) {
            selW.value = i;
            if (selW.callback) selW.callback(i);
            this.setDirtyCanvas(true, true);
            return true;
          }
        }
      }
      return prevDown ? prevDown.apply(this, arguments) : false;
    };

    const apply = () => {
      const count = Math.max(2, Math.min(MAX, parseInt(countW.value) || 2));
      rows.forEach((w, k) => {
        const hide = k + 1 > count;
        setHidden(w, hide);
        setSlotHidden(node, "value_" + (k + 1), hide);
      });
      if (Number(selW.value) > count) selW.value = count;
      if (Number(selW.value) < 1) selW.value = 1;
      setHidden(selW, true);
      setSlotHidden(node, "selected", true);
      const size = node.computeSize();
      node.setSize([Math.max(node.size[0], size[0]), size[1]]);
      app.graph.setDirtyCanvas(true, true);
    };

    countW.callback = apply;
    const prevCfg = node.onConfigure;
    node.onConfigure = function () {
      const r = prevCfg ? prevCfg.apply(this, arguments) : undefined;
      apply();
      return r;
    };
    apply();
  },
});
