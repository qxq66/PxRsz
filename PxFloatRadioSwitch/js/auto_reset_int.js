import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_TYPE = "AutoResetInt";
const BADGE_H = 20;
const BADGE_TICK_MS = 100;

const getARNodes = () => {
    const nodes = app.graph?.nodes || app.graph?._nodes || [];
    return nodes.filter(n => n.type === NODE_TYPE);
};

function findIntWidget(node, name) {
    const outer = node.widgets?.find(w => w.name === name);
    if (!outer) return null;
    if (Array.isArray(outer.widgets)) return outer.widgets[0];
    if (outer.widget && typeof outer.widget === "object") return outer.widget;
    return outer;
}

function getResetTarget(node) {
    const targetW = node.widgets?.find(w => w.name === "reset_value");
    return targetW ? targetW.value : 0;
}

app.registerExtension({
    name: "Comfy.AutoResetInt",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_TYPE) return;

        const _onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            _onCreated?.apply(this, arguments);

            this._ariTimer = null;
            this._ariTickTimer = null;
            this._ariTimerEnd = null;
            this._ariBadgeText = "";
            this._ariBadgeClr = "rgba(40,160,80,0.85)";

            const modeW = this.widgets?.find(w => w.name === "reset_mode");
            const delayW = this.widgets?.find(w => w.name === "reset_delay_seconds");

            const syncVis = () => {
                if (!delayW) return;
                delayW.hidden = modeW?.value !== "Manual";
                this.setSize(this.computeSize());
                app.graph?.setDirtyCanvas(true, true);
            };
            if (modeW) {
                syncVis();
                const _cb = modeW.callback;
                modeW.callback = (v, ...rest) => {
                    _cb?.call(this, v, ...rest);
                    syncVis();
                };
            }
        };

        const _onDrawFg = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (ctx) {
            _onDrawFg?.apply(this, arguments);
            if (!this._ariBadgeText) return;
            const [nw, nh] = this.size;
            ctx.save();
            ctx.fillStyle = this._ariBadgeClr;
            ctx.beginPath();
            ctx.roundRect(4, nh - BADGE_H - 4, nw - 8, BADGE_H, 4);
            ctx.fill();
            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 11px monospace";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(this._ariBadgeText, nw / 2, nh - BADGE_H / 2 - 4);
            ctx.restore();
        };

        const _onRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            _onRemoved?.apply(this, arguments);
            this._clearAriTimer?.();
        };

        nodeType.prototype._clearAriTimer = function () {
            if (this._ariTimer) { clearTimeout(this._ariTimer); this._ariTimer = null; }
            if (this._ariTickTimer) { clearTimeout(this._ariTickTimer); this._ariTickTimer = null; }
            this._ariTimerEnd = null;
            this._ariBadgeText = "";
            app.graph?.setDirtyCanvas(true, true);
        };
    },

    setup() {
        function applyInstantReset(node, reason = "interrupted") {
            const valW = findIntWidget(node, "value");
            if (!valW) return;
            node._clearAriTimer();

            const resetVal = getResetTarget(node);
            valW.value = resetVal;
            valW.callback?.(resetVal);
            if (valW.element) valW.element.dispatchEvent(new Event("input"));

            node._ariBadgeText = `⚠ reset (${reason}) → ${resetVal}`;
            node._ariBadgeClr = "rgba(200,180,40,0.90)";
            app.graph?.setDirtyCanvas(true, true);

            node._ariTimer = setTimeout(() => {
                node._ariBadgeText = "";
                node._ariTimer = null;
                app.graph?.setDirtyCanvas(true, true);
            }, 3000);
        }

        function applyQueueEmptyReset(node) {
            const modeW = node.widgets?.find(w => w.name === "reset_mode");
            const delayW = node.widgets?.find(w => w.name === "reset_delay_seconds");
            const valW = findIntWidget(node, "value");
            if (!modeW || !valW) return;

            node._clearAriTimer();
            const resetVal = getResetTarget(node);

            if (modeW.value === "Auto") {
                valW.value = resetVal;
                valW.callback?.(resetVal);
                if (valW.element) valW.element.dispatchEvent(new Event("input"));
                node._ariBadgeText = `✔ auto reset → ${resetVal}`;
                node._ariBadgeClr = "rgba(40,160,80,0.85)";
                app.graph?.setDirtyCanvas(true, true);
                node._ariTimer = setTimeout(() => {
                    node._ariBadgeText = "";
                    node._ariTimer = null;
                    app.graph?.setDirtyCanvas(true, true);
                }, 3000);
            } else if (modeW.value === "Manual") {
                const delaySec = Math.max(1, delayW?.value ?? 3);
                const delayMs = delaySec * 1000;
                node._ariTimerEnd = Date.now() + delayMs;
                node._ariBadgeClr = "rgba(200,120,20,0.90)";

                const tick = () => {
                    if (!node._ariTimerEnd) return;
                    const left = node._ariTimerEnd - Date.now();
                    if (left <= 0) return;
                    node._ariBadgeText = `⏱ reset in ${(left / 1000).toFixed(1)} s`;
                    app.graph?.setDirtyCanvas(true, true);
                    node._ariTickTimer = setTimeout(tick, BADGE_TICK_MS);
                };
                tick();

                node._ariTimer = setTimeout(() => {
                    clearTimeout(node._ariTickTimer);
                    node._ariTickTimer = null;
                    node._ariTimerEnd = null;
                    node._ariTimer = null;

                    valW.value = resetVal;
                    valW.callback?.(resetVal);
                    if (valW.element) valW.element.dispatchEvent(new Event("input"));
                    node._ariBadgeText = `✔ manual reset → ${resetVal}`;
                    node._ariBadgeClr = "rgba(40,160,80,0.85)";
                    app.graph?.setDirtyCanvas(true, true);
                    node._ariTimer = setTimeout(() => {
                        node._ariBadgeText = "";
                        node._ariTimer = null;
                        app.graph?.setDirtyCanvas(true, true);
                    }, 3000);
                }, delayMs);
            }
        }

        api.addEventListener("execution_success", async () => {
            await new Promise(r => setTimeout(r, 200));
            let running = 1, pending = 1;
            try {
                const q = await api.getQueue();
                running = q.queue_running?.length ?? 0;
                pending = q.queue_pending?.length ?? 0;
            } catch (e) {
                console.warn("[AutoResetInt] getQueue failed:", e);
                return;
            }
            if (running + pending === 0) {
                for (const node of getARNodes()) {
                    applyQueueEmptyReset(node);
                }
            }
        });

        api.addEventListener("execution_interrupted", () => {
            for (const node of getARNodes()) {
                applyInstantReset(node, "interrupted");
            }
        });
    },
});
