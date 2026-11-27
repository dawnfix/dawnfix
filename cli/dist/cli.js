#!/usr/bin/env node
// Dawnfix 0.3.1: npx dawnfix init | doctor | flare.
// Source available under FSL-1.1-ALv2 (see LICENSE in this package).
// GENERATED from cli/src/ and flare/src/ by `npm run build` (esbuild, one file, no dependencies). Do not edit.
import { createRequire as __dawnfixRequire } from 'node:module';
const require = __dawnfixRequire(import.meta.url);
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __require = /* @__PURE__ */ ((x) => typeof require !== "undefined" ? require : typeof Proxy !== "undefined" ? new Proxy(x, {
  get: (a, b) => (typeof require !== "undefined" ? require : a)[b]
}) : x)(function(x) {
  if (typeof require !== "undefined") return require.apply(this, arguments);
  throw Error('Dynamic require of "' + x + '" is not supported');
});
var __commonJS = (cb, mod) => function __require2() {
  try {
    return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
  } catch (e) {
    throw mod = 0, e;
  }
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));

// node_modules/yaml/dist/nodes/identity.js
var require_identity = __commonJS({
  "node_modules/yaml/dist/nodes/identity.js"(exports) {
    "use strict";
    var ALIAS = /* @__PURE__ */ Symbol.for("yaml.alias");
    var DOC = /* @__PURE__ */ Symbol.for("yaml.document");
    var MAP = /* @__PURE__ */ Symbol.for("yaml.map");
    var PAIR = /* @__PURE__ */ Symbol.for("yaml.pair");
    var SCALAR = /* @__PURE__ */ Symbol.for("yaml.scalar");
    var SEQ = /* @__PURE__ */ Symbol.for("yaml.seq");
    var NODE_TYPE = /* @__PURE__ */ Symbol.for("yaml.node.type");
    var isAlias = (node) => !!node && typeof node === "object" && node[NODE_TYPE] === ALIAS;
    var isDocument = (node) => !!node && typeof node === "object" && node[NODE_TYPE] === DOC;
    var isMap = (node) => !!node && typeof node === "object" && node[NODE_TYPE] === MAP;
    var isPair = (node) => !!node && typeof node === "object" && node[NODE_TYPE] === PAIR;
    var isScalar = (node) => !!node && typeof node === "object" && node[NODE_TYPE] === SCALAR;
    var isSeq = (node) => !!node && typeof node === "object" && node[NODE_TYPE] === SEQ;
    function isCollection(node) {
      if (node && typeof node === "object")
        switch (node[NODE_TYPE]) {
          case MAP:
          case SEQ:
            return true;
        }
      return false;
    }
    function isNode(node) {
      if (node && typeof node === "object")
        switch (node[NODE_TYPE]) {
          case ALIAS:
          case MAP:
          case SCALAR:
          case SEQ:
            return true;
        }
      return false;
    }
    var hasAnchor = (node) => (isScalar(node) || isCollection(node)) && !!node.anchor;
    exports.ALIAS = ALIAS;
    exports.DOC = DOC;
    exports.MAP = MAP;
    exports.NODE_TYPE = NODE_TYPE;
    exports.PAIR = PAIR;
    exports.SCALAR = SCALAR;
    exports.SEQ = SEQ;
    exports.hasAnchor = hasAnchor;
    exports.isAlias = isAlias;
    exports.isCollection = isCollection;
    exports.isDocument = isDocument;
    exports.isMap = isMap;
    exports.isNode = isNode;
    exports.isPair = isPair;
    exports.isScalar = isScalar;
    exports.isSeq = isSeq;
  }
});

// node_modules/yaml/dist/visit.js
var require_visit = __commonJS({
  "node_modules/yaml/dist/visit.js"(exports) {
    "use strict";
    var identity = require_identity();
    var BREAK = /* @__PURE__ */ Symbol("break visit");
    var SKIP = /* @__PURE__ */ Symbol("skip children");
    var REMOVE = /* @__PURE__ */ Symbol("remove node");
    function visit(node, visitor) {
      const visitor_ = initVisitor(visitor);
      if (identity.isDocument(node)) {
        const cd = visit_(null, node.contents, visitor_, Object.freeze([node]));
        if (cd === REMOVE)
          node.contents = null;
      } else
        visit_(null, node, visitor_, Object.freeze([]));
    }
    visit.BREAK = BREAK;
    visit.SKIP = SKIP;
    visit.REMOVE = REMOVE;
    function visit_(key, node, visitor, path) {
      const ctrl = callVisitor(key, node, visitor, path);
      if (identity.isNode(ctrl) || identity.isPair(ctrl)) {
        replaceNode(key, path, ctrl);
        return visit_(key, ctrl, visitor, path);
      }
      if (typeof ctrl !== "symbol") {
        if (identity.isCollection(node)) {
          path = Object.freeze(path.concat(node));
          for (let i = 0; i < node.items.length; ++i) {
            const ci = visit_(i, node.items[i], visitor, path);
            if (typeof ci === "number")
              i = ci - 1;
            else if (ci === BREAK)
              return BREAK;
            else if (ci === REMOVE) {
              node.items.splice(i, 1);
              i -= 1;
            }
          }
        } else if (identity.isPair(node)) {
          path = Object.freeze(path.concat(node));
          const ck = visit_("key", node.key, visitor, path);
          if (ck === BREAK)
            return BREAK;
          else if (ck === REMOVE)
            node.key = null;
          const cv = visit_("value", node.value, visitor, path);
          if (cv === BREAK)
            return BREAK;
          else if (cv === REMOVE)
            node.value = null;
        }
      }
      return ctrl;
    }
    async function visitAsync(node, visitor) {
      const visitor_ = initVisitor(visitor);
      if (identity.isDocument(node)) {
        const cd = await visitAsync_(null, node.contents, visitor_, Object.freeze([node]));
        if (cd === REMOVE)
          node.contents = null;
      } else
        await visitAsync_(null, node, visitor_, Object.freeze([]));
    }
    visitAsync.BREAK = BREAK;
    visitAsync.SKIP = SKIP;
    visitAsync.REMOVE = REMOVE;
    async function visitAsync_(key, node, visitor, path) {
      const ctrl = await callVisitor(key, node, visitor, path);
      if (identity.isNode(ctrl) || identity.isPair(ctrl)) {
        replaceNode(key, path, ctrl);
        return visitAsync_(key, ctrl, visitor, path);
      }
      if (typeof ctrl !== "symbol") {
        if (identity.isCollection(node)) {
          path = Object.freeze(path.concat(node));
          for (let i = 0; i < node.items.length; ++i) {
            const ci = await visitAsync_(i, node.items[i], visitor, path);
            if (typeof ci === "number")
              i = ci - 1;
            else if (ci === BREAK)
              return BREAK;
            else if (ci === REMOVE) {
              node.items.splice(i, 1);
              i -= 1;
            }
          }
        } else if (identity.isPair(node)) {
          path = Object.freeze(path.concat(node));
          const ck = await visitAsync_("key", node.key, visitor, path);
          if (ck === BREAK)
            return BREAK;
          else if (ck === REMOVE)
            node.key = null;
          const cv = await visitAsync_("value", node.value, visitor, path);
          if (cv === BREAK)
            return BREAK;
          else if (cv === REMOVE)
            node.value = null;
        }
      }
      return ctrl;
    }
    function initVisitor(visitor) {
      if (typeof visitor === "object" && (visitor.Collection || visitor.Node || visitor.Value)) {
        return Object.assign({
          Alias: visitor.Node,
          Map: visitor.Node,
          Scalar: visitor.Node,
          Seq: visitor.Node
        }, visitor.Value && {
          Map: visitor.Value,
          Scalar: visitor.Value,
          Seq: visitor.Value
        }, visitor.Collection && {
          Map: visitor.Collection,
          Seq: visitor.Collection
        }, visitor);
      }
      return visitor;
    }
    function callVisitor(key, node, visitor, path) {
      if (typeof visitor === "function")
        return visitor(key, node, path);
      if (identity.isMap(node))
        return visitor.Map?.(key, node, path);
      if (identity.isSeq(node))
        return visitor.Seq?.(key, node, path);
      if (identity.isPair(node))
        return visitor.Pair?.(key, node, path);
      if (identity.isScalar(node))
        return visitor.Scalar?.(key, node, path);
      if (identity.isAlias(node))
        return visitor.Alias?.(key, node, path);
      return void 0;
    }
    function replaceNode(key, path, node) {
      const parent = path[path.length - 1];
      if (identity.isCollection(parent)) {
        parent.items[key] = node;
      } else if (identity.isPair(parent)) {
        if (key === "key")
          parent.key = node;
        else
          parent.value = node;
      } else if (identity.isDocument(parent)) {
        parent.contents = node;
      } else {
        const pt = identity.isAlias(parent) ? "alias" : "scalar";
        throw new Error(`Cannot replace node with ${pt} parent`);
      }
    }
    exports.visit = visit;
    exports.visitAsync = visitAsync;
  }
});

// node_modules/yaml/dist/doc/directives.js
var require_directives = __commonJS({
  "node_modules/yaml/dist/doc/directives.js"(exports) {
    "use strict";
    var identity = require_identity();
    var visit = require_visit();
    var escapeChars = {
      "!": "%21",
      ",": "%2C",
      "[": "%5B",
      "]": "%5D",
      "{": "%7B",
      "}": "%7D"
    };
    var escapeTagName = (tn) => tn.replace(/[!,[\]{}]/g, (ch) => escapeChars[ch]);
    var Directives = class _Directives {
      constructor(yaml, tags) {
        this.docStart = null;
        this.docEnd = false;
        this.yaml = Object.assign({}, _Directives.defaultYaml, yaml);
        this.tags = Object.assign({}, _Directives.defaultTags, tags);
      }
      clone() {
        const copy = new _Directives(this.yaml, this.tags);
        copy.docStart = this.docStart;
        return copy;
      }
      /**
       * During parsing, get a Directives instance for the current document and
       * update the stream state according to the current version's spec.
       */
      atDocument() {
        const res = new _Directives(this.yaml, this.tags);
        switch (this.yaml.version) {
          case "1.1":
            this.atNextDocument = true;
            break;
          case "1.2":
            this.atNextDocument = false;
            this.yaml = {
              explicit: _Directives.defaultYaml.explicit,
              version: "1.2"
            };
            this.tags = Object.assign({}, _Directives.defaultTags);
            break;
        }
        return res;
      }
      /**
       * @param onError - May be called even if the action was successful
       * @returns `true` on success
       */
      add(line, onError) {
        if (this.atNextDocument) {
          this.yaml = { explicit: _Directives.defaultYaml.explicit, version: "1.1" };
          this.tags = Object.assign({}, _Directives.defaultTags);
          this.atNextDocument = false;
        }
        const parts = line.trim().split(/[ \t]+/);
        const name = parts.shift();
        switch (name) {
          case "%TAG": {
            if (parts.length !== 2) {
              onError(0, "%TAG directive should contain exactly two parts");
              if (parts.length < 2)
                return false;
            }
            const [handle, prefix] = parts;
            this.tags[handle] = prefix;
            return true;
          }
          case "%YAML": {
            this.yaml.explicit = true;
            if (parts.length !== 1) {
              onError(0, "%YAML directive should contain exactly one part");
              return false;
            }
            const [version] = parts;
            if (version === "1.1" || version === "1.2") {
              this.yaml.version = version;
              return true;
            } else {
              const isValid = /^\d+\.\d+$/.test(version);
              onError(6, `Unsupported YAML version ${version}`, isValid);
              return false;
            }
          }
          default:
            onError(0, `Unknown directive ${name}`, true);
            return false;
        }
      }
      /**
       * Resolves a tag, matching handles to those defined in %TAG directives.
       *
       * @returns Resolved tag, which may also be the non-specific tag `'!'` or a
       *   `'!local'` tag, or `null` if unresolvable.
       */
      tagName(source, onError) {
        if (source === "!")
          return "!";
        if (source[0] !== "!") {
          onError(`Not a valid tag: ${source}`);
          return null;
        }
        if (source[1] === "<") {
          const verbatim = source.slice(2, -1);
          if (verbatim === "!" || verbatim === "!!") {
            onError(`Verbatim tags aren't resolved, so ${source} is invalid.`);
            return null;
          }
          if (source[source.length - 1] !== ">")
            onError("Verbatim tags must end with a >");
          return verbatim;
        }
        const [, handle, suffix] = source.match(/^(.*!)([^!]*)$/s);
        if (!suffix)
          onError(`The ${source} tag has no suffix`);
        const prefix = this.tags[handle];
        if (prefix) {
          try {
            return prefix + decodeURIComponent(suffix);
          } catch (error) {
            onError(String(error));
            return null;
          }
        }
        if (handle === "!")
          return source;
        onError(`Could not resolve tag: ${source}`);
        return null;
      }
      /**
       * Given a fully resolved tag, returns its printable string form,
       * taking into account current tag prefixes and defaults.
       */
      tagString(tag) {
        for (const [handle, prefix] of Object.entries(this.tags)) {
          if (tag.startsWith(prefix))
            return handle + escapeTagName(tag.substring(prefix.length));
        }
        return tag[0] === "!" ? tag : `!<${tag}>`;
      }
      toString(doc) {
        const lines = this.yaml.explicit ? [`%YAML ${this.yaml.version || "1.2"}`] : [];
        const tagEntries = Object.entries(this.tags);
        let tagNames;
        if (doc && tagEntries.length > 0 && identity.isNode(doc.contents)) {
          const tags = {};
          visit.visit(doc.contents, (_key, node) => {
            if (identity.isNode(node) && node.tag)
              tags[node.tag] = true;
          });
          tagNames = Object.keys(tags);
        } else
          tagNames = [];
        for (const [handle, prefix] of tagEntries) {
          if (handle === "!!" && prefix === "tag:yaml.org,2002:")
            continue;
          if (!doc || tagNames.some((tn) => tn.startsWith(prefix)))
            lines.push(`%TAG ${handle} ${prefix}`);
        }
        return lines.join("\n");
      }
    };
    Directives.defaultYaml = { explicit: false, version: "1.2" };
    Directives.defaultTags = { "!!": "tag:yaml.org,2002:" };
    exports.Directives = Directives;
  }
});

// node_modules/yaml/dist/doc/anchors.js
var require_anchors = __commonJS({
  "node_modules/yaml/dist/doc/anchors.js"(exports) {
    "use strict";
    var identity = require_identity();
    var visit = require_visit();
    function anchorIsValid(anchor) {
      if (/[\x00-\x19\s,[\]{}]/.test(anchor)) {
        const sa = JSON.stringify(anchor);
        const msg = `Anchor must not contain whitespace or control characters: ${sa}`;
        throw new Error(msg);
      }
      return true;
    }
    function anchorNames(root) {
      const anchors = /* @__PURE__ */ new Set();
      visit.visit(root, {
        Value(_key, node) {
          if (node.anchor)
            anchors.add(node.anchor);
        }
      });
      return anchors;
    }
    function findNewAnchor(prefix, exclude) {
      for (let i = 1; true; ++i) {
        const name = `${prefix}${i}`;
        if (!exclude.has(name))
          return name;
      }
    }
    function createNodeAnchors(doc, prefix) {
      const aliasObjects = [];
      const sourceObjects = /* @__PURE__ */ new Map();
      let prevAnchors = null;
      return {
        onAnchor: (source) => {
          aliasObjects.push(source);
          prevAnchors ?? (prevAnchors = anchorNames(doc));
          const anchor = findNewAnchor(prefix, prevAnchors);
          prevAnchors.add(anchor);
          return anchor;
        },
        /**
         * With circular references, the source node is only resolved after all
         * of its child nodes are. This is why anchors are set only after all of
         * the nodes have been created.
         */
        setAnchors: () => {
          for (const source of aliasObjects) {
            const ref = sourceObjects.get(source);
            if (typeof ref === "object" && ref.anchor && (identity.isScalar(ref.node) || identity.isCollection(ref.node))) {
              ref.node.anchor = ref.anchor;
            } else {
              const error = new Error("Failed to resolve repeated object (this should not happen)");
              error.source = source;
              throw error;
            }
          }
        },
        sourceObjects
      };
    }
    exports.anchorIsValid = anchorIsValid;
    exports.anchorNames = anchorNames;
    exports.createNodeAnchors = createNodeAnchors;
    exports.findNewAnchor = findNewAnchor;
  }
});

// node_modules/yaml/dist/doc/applyReviver.js
var require_applyReviver = __commonJS({
  "node_modules/yaml/dist/doc/applyReviver.js"(exports) {
    "use strict";
    function applyReviver(reviver, obj, key, val) {
      if (val && typeof val === "object") {
        if (Array.isArray(val)) {
          for (let i = 0, len = val.length; i < len; ++i) {
            const v0 = val[i];
            const v1 = applyReviver(reviver, val, String(i), v0);
            if (v1 === void 0)
              delete val[i];
            else if (v1 !== v0)
              val[i] = v1;
          }
        } else if (val instanceof Map) {
          for (const k of Array.from(val.keys())) {
            const v0 = val.get(k);
            const v1 = applyReviver(reviver, val, k, v0);
            if (v1 === void 0)
              val.delete(k);
            else if (v1 !== v0)
              val.set(k, v1);
          }
        } else if (val instanceof Set) {
          for (const v0 of Array.from(val)) {
            const v1 = applyReviver(reviver, val, v0, v0);
            if (v1 === void 0)
              val.delete(v0);
            else if (v1 !== v0) {
              val.delete(v0);
              val.add(v1);
            }
          }
        } else {
          for (const [k, v0] of Object.entries(val)) {
            const v1 = applyReviver(reviver, val, k, v0);
            if (v1 === void 0)
              delete val[k];
            else if (v1 !== v0)
              val[k] = v1;
          }
        }
      }
      return reviver.call(obj, key, val);
    }
    exports.applyReviver = applyReviver;
  }
});

// node_modules/yaml/dist/nodes/toJS.js
var require_toJS = __commonJS({
  "node_modules/yaml/dist/nodes/toJS.js"(exports) {
    "use strict";
    var identity = require_identity();
    function toJS(value, arg, ctx) {
      if (Array.isArray(value))
        return value.map((v, i) => toJS(v, String(i), ctx));
      if (value && typeof value.toJSON === "function") {
        if (!ctx || !identity.hasAnchor(value))
          return value.toJSON(arg, ctx);
        const data = { aliasCount: 0, count: 1, res: void 0 };
        ctx.anchors.set(value, data);
        ctx.onCreate = (res2) => {
          data.res = res2;
          delete ctx.onCreate;
        };
        const res = value.toJSON(arg, ctx);
        if (ctx.onCreate)
          ctx.onCreate(res);
        return res;
      }
      if (typeof value === "bigint" && !ctx?.keep)
        return Number(value);
      return value;
    }
    exports.toJS = toJS;
  }
});

// node_modules/yaml/dist/nodes/Node.js
var require_Node = __commonJS({
  "node_modules/yaml/dist/nodes/Node.js"(exports) {
    "use strict";
    var applyReviver = require_applyReviver();
    var identity = require_identity();
    var toJS = require_toJS();
    var NodeBase = class {
      constructor(type) {
        Object.defineProperty(this, identity.NODE_TYPE, { value: type });
      }
      /** Create a copy of this node.  */
      clone() {
        const copy = Object.create(Object.getPrototypeOf(this), Object.getOwnPropertyDescriptors(this));
        if (this.range)
          copy.range = this.range.slice();
        return copy;
      }
      /** A plain JavaScript representation of this node. */
      toJS(doc, { mapAsMap, maxAliasCount, onAnchor, reviver } = {}) {
        if (!identity.isDocument(doc))
          throw new TypeError("A document argument is required");
        const ctx = {
          anchors: /* @__PURE__ */ new Map(),
          doc,
          keep: true,
          mapAsMap: mapAsMap === true,
          mapKeyWarned: false,
          maxAliasCount: typeof maxAliasCount === "number" ? maxAliasCount : 100
        };
        const res = toJS.toJS(this, "", ctx);
        if (typeof onAnchor === "function")
          for (const { count, res: res2 } of ctx.anchors.values())
            onAnchor(res2, count);
        return typeof reviver === "function" ? applyReviver.applyReviver(reviver, { "": res }, "", res) : res;
      }
    };
    exports.NodeBase = NodeBase;
  }
});

// node_modules/yaml/dist/nodes/Alias.js
var require_Alias = __commonJS({
  "node_modules/yaml/dist/nodes/Alias.js"(exports) {
    "use strict";
    var anchors = require_anchors();
    var visit = require_visit();
    var identity = require_identity();
    var Node = require_Node();
    var toJS = require_toJS();
    var Alias = class extends Node.NodeBase {
      constructor(source) {
        super(identity.ALIAS);
        this.source = source;
        Object.defineProperty(this, "tag", {
          set() {
            throw new Error("Alias nodes cannot have tags");
          }
        });
      }
      /**
       * Resolve the value of this alias within `doc`, finding the last
       * instance of the `source` anchor before this node.
       */
      resolve(doc, ctx) {
        if (ctx?.maxAliasCount === 0)
          throw new ReferenceError("Alias resolution is disabled");
        let nodes;
        if (ctx?.aliasResolveCache) {
          nodes = ctx.aliasResolveCache;
        } else {
          nodes = [];
          visit.visit(doc, {
            Node: (_key, node) => {
              if (identity.isAlias(node) || identity.hasAnchor(node))
                nodes.push(node);
            }
          });
          if (ctx)
            ctx.aliasResolveCache = nodes;
        }
        let found = void 0;
        for (const node of nodes) {
          if (node === this)
            break;
          if (node.anchor === this.source)
            found = node;
        }
        if (found && ctx) {
          const { anchors: anchors2, doc: doc2, maxAliasCount } = ctx;
          let data = anchors2.get(found);
          if (!data) {
            toJS.toJS(found, null, ctx);
            data = anchors2.get(found);
          }
          if (data?.res === void 0) {
            const msg = "This should not happen: Alias anchor was not resolved?";
            throw new ReferenceError(msg);
          }
          if (maxAliasCount >= 0) {
            data.count += 1;
            if (data.aliasCount === 0)
              data.aliasCount = getAliasCount(doc2, found, anchors2);
            if (data.count * data.aliasCount > maxAliasCount) {
              const msg = "Excessive alias count indicates a resource exhaustion attack";
              throw new ReferenceError(msg);
            }
          }
        }
        return found;
      }
      toJSON(_arg, ctx) {
        if (!ctx)
          return { source: this.source };
        const source = this.resolve(ctx.doc, ctx);
        if (!source) {
          const msg = `Unresolved alias (the anchor must be set before the alias): ${this.source}`;
          throw new ReferenceError(msg);
        }
        return ctx.anchors.get(source).res;
      }
      toString(ctx, _onComment, _onChompKeep) {
        const src = `*${this.source}`;
        if (ctx) {
          anchors.anchorIsValid(this.source);
          if (ctx.options.verifyAliasOrder && !ctx.anchors.has(this.source)) {
            const msg = `Unresolved alias (the anchor must be set before the alias): ${this.source}`;
            throw new Error(msg);
          }
          if (ctx.implicitKey)
            return `${src} `;
        }
        return src;
      }
    };
    function getAliasCount(doc, node, anchors2) {
      if (identity.isAlias(node)) {
        const source = node.resolve(doc);
        const anchor = anchors2 && source && anchors2.get(source);
        return anchor ? anchor.count * anchor.aliasCount : 0;
      } else if (identity.isCollection(node)) {
        let count = 0;
        for (const item of node.items) {
          const c = getAliasCount(doc, item, anchors2);
          if (c > count)
            count = c;
        }
        return count;
      } else if (identity.isPair(node)) {
        const kc = getAliasCount(doc, node.key, anchors2);
        const vc = getAliasCount(doc, node.value, anchors2);
        return Math.max(kc, vc);
      }
      return 1;
    }
    exports.Alias = Alias;
  }
});

// node_modules/yaml/dist/nodes/Scalar.js
var require_Scalar = __commonJS({
  "node_modules/yaml/dist/nodes/Scalar.js"(exports) {
    "use strict";
    var identity = require_identity();
    var Node = require_Node();
    var toJS = require_toJS();
    var isScalarValue = (value) => !value || typeof value !== "function" && typeof value !== "object";
    var Scalar = class extends Node.NodeBase {
      constructor(value) {
        super(identity.SCALAR);
        this.value = value;
      }
      toJSON(arg, ctx) {
        return ctx?.keep ? this.value : toJS.toJS(this.value, arg, ctx);
      }
      toString() {
        return String(this.value);
      }
    };
    Scalar.BLOCK_FOLDED = "BLOCK_FOLDED";
    Scalar.BLOCK_LITERAL = "BLOCK_LITERAL";
    Scalar.PLAIN = "PLAIN";
    Scalar.QUOTE_DOUBLE = "QUOTE_DOUBLE";
    Scalar.QUOTE_SINGLE = "QUOTE_SINGLE";
    exports.Scalar = Scalar;
    exports.isScalarValue = isScalarValue;
  }
});

// node_modules/yaml/dist/doc/createNode.js
var require_createNode = __commonJS({
  "node_modules/yaml/dist/doc/createNode.js"(exports) {
    "use strict";
    var Alias = require_Alias();
    var identity = require_identity();
    var Scalar = require_Scalar();
    var defaultTagPrefix = "tag:yaml.org,2002:";
    function findTagObject(value, tagName, tags) {
      if (tagName) {
        const match = tags.filter((t) => t.tag === tagName);
        const tagObj = match.find((t) => !t.format) ?? match[0];
        if (!tagObj)
          throw new Error(`Tag ${tagName} not found`);
        return tagObj;
      }
      return tags.find((t) => t.identify?.(value) && !t.format);
    }
    function createNode(value, tagName, ctx) {
      if (identity.isDocument(value))
        value = value.contents;
      if (identity.isNode(value))
        return value;
      if (identity.isPair(value)) {
        const map = ctx.schema[identity.MAP].createNode?.(ctx.schema, null, ctx);
        map.items.push(value);
        return map;
      }
      if (value instanceof String || value instanceof Number || value instanceof Boolean || typeof BigInt !== "undefined" && value instanceof BigInt) {
        value = value.valueOf();
      }
      const { aliasDuplicateObjects, onAnchor, onTagObj, schema, sourceObjects } = ctx;
      let ref = void 0;
      if (aliasDuplicateObjects && value && typeof value === "object") {
        ref = sourceObjects.get(value);
        if (ref) {
          ref.anchor ?? (ref.anchor = onAnchor(value));
          return new Alias.Alias(ref.anchor);
        } else {
          ref = { anchor: null, node: null };
          sourceObjects.set(value, ref);
        }
      }
      if (tagName?.startsWith("!!"))
        tagName = defaultTagPrefix + tagName.slice(2);
      let tagObj = findTagObject(value, tagName, schema.tags);
      if (!tagObj) {
        if (value && typeof value.toJSON === "function") {
          value = value.toJSON();
        }
        if (!value || typeof value !== "object") {
          const node2 = new Scalar.Scalar(value);
          if (ref)
            ref.node = node2;
          return node2;
        }
        tagObj = value instanceof Map ? schema[identity.MAP] : Symbol.iterator in Object(value) ? schema[identity.SEQ] : schema[identity.MAP];
      }
      if (onTagObj) {
        onTagObj(tagObj);
        delete ctx.onTagObj;
      }
      const node = tagObj?.createNode ? tagObj.createNode(ctx.schema, value, ctx) : typeof tagObj?.nodeClass?.from === "function" ? tagObj.nodeClass.from(ctx.schema, value, ctx) : new Scalar.Scalar(value);
      if (tagName)
        node.tag = tagName;
      else if (!tagObj.default)
        node.tag = tagObj.tag;
      if (ref)
        ref.node = node;
      return node;
    }
    exports.createNode = createNode;
  }
});

// node_modules/yaml/dist/nodes/Collection.js
var require_Collection = __commonJS({
  "node_modules/yaml/dist/nodes/Collection.js"(exports) {
    "use strict";
    var createNode = require_createNode();
    var identity = require_identity();
    var Node = require_Node();
    function collectionFromPath(schema, path, value) {
      let v = value;
      for (let i = path.length - 1; i >= 0; --i) {
        const k = path[i];
        if (typeof k === "number" && Number.isInteger(k) && k >= 0) {
          const a = [];
          a[k] = v;
          v = a;
        } else {
          v = /* @__PURE__ */ new Map([[k, v]]);
        }
      }
      return createNode.createNode(v, void 0, {
        aliasDuplicateObjects: false,
        keepUndefined: false,
        onAnchor: () => {
          throw new Error("This should not happen, please report a bug.");
        },
        schema,
        sourceObjects: /* @__PURE__ */ new Map()
      });
    }
    var isEmptyPath = (path) => path == null || typeof path === "object" && !!path[Symbol.iterator]().next().done;
    var Collection = class extends Node.NodeBase {
      constructor(type, schema) {
        super(type);
        Object.defineProperty(this, "schema", {
          value: schema,
          configurable: true,
          enumerable: false,
          writable: true
        });
      }
      /**
       * Create a copy of this collection.
       *
       * @param schema - If defined, overwrites the original's schema
       */
      clone(schema) {
        const copy = Object.create(Object.getPrototypeOf(this), Object.getOwnPropertyDescriptors(this));
        if (schema)
          copy.schema = schema;
        copy.items = copy.items.map((it) => identity.isNode(it) || identity.isPair(it) ? it.clone(schema) : it);
        if (this.range)
          copy.range = this.range.slice();
        return copy;
      }
      /**
       * Adds a value to the collection. For `!!map` and `!!omap` the value must
       * be a Pair instance or a `{ key, value }` object, which may not have a key
       * that already exists in the map.
       */
      addIn(path, value) {
        if (isEmptyPath(path))
          this.add(value);
        else {
          const [key, ...rest] = path;
          const node = this.get(key, true);
          if (identity.isCollection(node))
            node.addIn(rest, value);
          else if (node === void 0 && this.schema)
            this.set(key, collectionFromPath(this.schema, rest, value));
          else
            throw new Error(`Expected YAML collection at ${key}. Remaining path: ${rest}`);
        }
      }
      /**
       * Removes a value from the collection.
       * @returns `true` if the item was found and removed.
       */
      deleteIn(path) {
        const [key, ...rest] = path;
        if (rest.length === 0)
          return this.delete(key);
        const node = this.get(key, true);
        if (identity.isCollection(node))
          return node.deleteIn(rest);
        else
          throw new Error(`Expected YAML collection at ${key}. Remaining path: ${rest}`);
      }
      /**
       * Returns item at `key`, or `undefined` if not found. By default unwraps
       * scalar values from their surrounding node; to disable set `keepScalar` to
       * `true` (collections are always returned intact).
       */
      getIn(path, keepScalar) {
        const [key, ...rest] = path;
        const node = this.get(key, true);
        if (rest.length === 0)
          return !keepScalar && identity.isScalar(node) ? node.value : node;
        else
          return identity.isCollection(node) ? node.getIn(rest, keepScalar) : void 0;
      }
      hasAllNullValues(allowScalar) {
        return this.items.every((node) => {
          if (!identity.isPair(node))
            return false;
          const n = node.value;
          return n == null || allowScalar && identity.isScalar(n) && n.value == null && !n.commentBefore && !n.comment && !n.tag;
        });
      }
      /**
       * Checks if the collection includes a value with the key `key`.
       */
      hasIn(path) {
        const [key, ...rest] = path;
        if (rest.length === 0)
          return this.has(key);
        const node = this.get(key, true);
        return identity.isCollection(node) ? node.hasIn(rest) : false;
      }
      /**
       * Sets a value in this collection. For `!!set`, `value` needs to be a
       * boolean to add/remove the item from the set.
       */
      setIn(path, value) {
        const [key, ...rest] = path;
        if (rest.length === 0) {
          this.set(key, value);
        } else {
          const node = this.get(key, true);
          if (identity.isCollection(node))
            node.setIn(rest, value);
          else if (node === void 0 && this.schema)
            this.set(key, collectionFromPath(this.schema, rest, value));
          else
            throw new Error(`Expected YAML collection at ${key}. Remaining path: ${rest}`);
        }
      }
    };
    exports.Collection = Collection;
    exports.collectionFromPath = collectionFromPath;
    exports.isEmptyPath = isEmptyPath;
  }
});

// node_modules/yaml/dist/stringify/stringifyComment.js
var require_stringifyComment = __commonJS({
  "node_modules/yaml/dist/stringify/stringifyComment.js"(exports) {
    "use strict";
    var stringifyComment = (str) => str.replace(/^(?!$)(?: $)?/gm, "#");
    function indentComment(comment, indent) {
      if (/^\n+$/.test(comment))
        return comment.substring(1);
      return indent ? comment.replace(/^(?! *$)/gm, indent) : comment;
    }
    var lineComment = (str, indent, comment) => str.endsWith("\n") ? indentComment(comment, indent) : comment.includes("\n") ? "\n" + indentComment(comment, indent) : (str.endsWith(" ") ? "" : " ") + comment;
    exports.indentComment = indentComment;
    exports.lineComment = lineComment;
    exports.stringifyComment = stringifyComment;
  }
});

// node_modules/yaml/dist/stringify/foldFlowLines.js
var require_foldFlowLines = __commonJS({
  "node_modules/yaml/dist/stringify/foldFlowLines.js"(exports) {
    "use strict";
    var FOLD_FLOW = "flow";
    var FOLD_BLOCK = "block";
    var FOLD_QUOTED = "quoted";
    function foldFlowLines(text, indent, mode = "flow", { indentAtStart, lineWidth = 80, minContentWidth = 20, onFold, onOverflow } = {}) {
      if (!lineWidth || lineWidth < 0)
        return text;
      if (lineWidth < minContentWidth)
        minContentWidth = 0;
      const endStep = Math.max(1 + minContentWidth, 1 + lineWidth - indent.length);
      if (text.length <= endStep)
        return text;
      const folds = [];
      const escapedFolds = {};
      let end = lineWidth - indent.length;
      if (typeof indentAtStart === "number") {
        if (indentAtStart > lineWidth - Math.max(2, minContentWidth))
          folds.push(0);
        else
          end = lineWidth - indentAtStart;
      }
      let split = void 0;
      let prev = void 0;
      let overflow = false;
      let i = -1;
      let escStart = -1;
      let escEnd = -1;
      if (mode === FOLD_BLOCK) {
        i = consumeMoreIndentedLines(text, i, indent.length);
        if (i !== -1)
          end = i + endStep;
      }
      for (let ch; ch = text[i += 1]; ) {
        if (mode === FOLD_QUOTED && ch === "\\") {
          escStart = i;
          switch (text[i + 1]) {
            case "x":
              i += 3;
              break;
            case "u":
              i += 5;
              break;
            case "U":
              i += 9;
              break;
            default:
              i += 1;
          }
          escEnd = i;
        }
        if (ch === "\n") {
          if (mode === FOLD_BLOCK)
            i = consumeMoreIndentedLines(text, i, indent.length);
          end = i + indent.length + endStep;
          split = void 0;
        } else {
          if (ch === " " && prev && prev !== " " && prev !== "\n" && prev !== "	") {
            const next = text[i + 1];
            if (next && next !== " " && next !== "\n" && next !== "	")
              split = i;
          }
          if (i >= end) {
            if (split) {
              folds.push(split);
              end = split + endStep;
              split = void 0;
            } else if (mode === FOLD_QUOTED) {
              while (prev === " " || prev === "	") {
                prev = ch;
                ch = text[i += 1];
                overflow = true;
              }
              const j = i > escEnd + 1 ? i - 2 : escStart - 1;
              if (escapedFolds[j])
                return text;
              folds.push(j);
              escapedFolds[j] = true;
              end = j + endStep;
              split = void 0;
            } else {
              overflow = true;
            }
          }
        }
        prev = ch;
      }
      if (overflow && onOverflow)
        onOverflow();
      if (folds.length === 0)
        return text;
      if (onFold)
        onFold();
      let res = text.slice(0, folds[0]);
      for (let i2 = 0; i2 < folds.length; ++i2) {
        const fold = folds[i2];
        const end2 = folds[i2 + 1] || text.length;
        if (fold === 0)
          res = `
${indent}${text.slice(0, end2)}`;
        else {
          if (mode === FOLD_QUOTED && escapedFolds[fold])
            res += `${text[fold]}\\`;
          res += `
${indent}${text.slice(fold + 1, end2)}`;
        }
      }
      return res;
    }
    function consumeMoreIndentedLines(text, i, indent) {
      let end = i;
      let start = i + 1;
      let ch = text[start];
      while (ch === " " || ch === "	") {
        if (i < start + indent) {
          ch = text[++i];
        } else {
          do {
            ch = text[++i];
          } while (ch && ch !== "\n");
          end = i;
          start = i + 1;
          ch = text[start];
        }
      }
      return end;
    }
    exports.FOLD_BLOCK = FOLD_BLOCK;
    exports.FOLD_FLOW = FOLD_FLOW;
    exports.FOLD_QUOTED = FOLD_QUOTED;
    exports.foldFlowLines = foldFlowLines;
  }
});

// node_modules/yaml/dist/stringify/stringifyString.js
var require_stringifyString = __commonJS({
  "node_modules/yaml/dist/stringify/stringifyString.js"(exports) {
    "use strict";
    var Scalar = require_Scalar();
    var foldFlowLines = require_foldFlowLines();
    var getFoldOptions = (ctx, isBlock) => ({
      indentAtStart: isBlock ? ctx.indent.length : ctx.indentAtStart,
      lineWidth: ctx.options.lineWidth,
      minContentWidth: ctx.options.minContentWidth
    });
    var containsDocumentMarker = (str) => /^(%|---|\.\.\.)/m.test(str);
    function lineLengthOverLimit(str, lineWidth, indentLength) {
      if (!lineWidth || lineWidth < 0)
        return false;
      const limit = lineWidth - indentLength;
      const strLen = str.length;
      if (strLen <= limit)
        return false;
      for (let i = 0, start = 0; i < strLen; ++i) {
        if (str[i] === "\n") {
          if (i - start > limit)
            return true;
          start = i + 1;
          if (strLen - start <= limit)
            return false;
        }
      }
      return true;
    }
    function doubleQuotedString(value, ctx) {
      const json = JSON.stringify(value);
      if (ctx.options.doubleQuotedAsJSON)
        return json;
      const { implicitKey } = ctx;
      const minMultiLineLength = ctx.options.doubleQuotedMinMultiLineLength;
      const indent = ctx.indent || (containsDocumentMarker(value) ? "  " : "");
      let str = "";
      let start = 0;
      for (let i = 0, ch = json[i]; ch; ch = json[++i]) {
        if (ch === " " && json[i + 1] === "\\" && json[i + 2] === "n") {
          str += json.slice(start, i) + "\\ ";
          i += 1;
          start = i;
          ch = "\\";
        }
        if (ch === "\\")
          switch (json[i + 1]) {
            case "u":
              {
                str += json.slice(start, i);
                const code = json.substr(i + 2, 4);
                switch (code) {
                  case "0000":
                    str += "\\0";
                    break;
                  case "0007":
                    str += "\\a";
                    break;
                  case "000b":
                    str += "\\v";
                    break;
                  case "001b":
                    str += "\\e";
                    break;
                  case "0085":
                    str += "\\N";
                    break;
                  case "00a0":
                    str += "\\_";
                    break;
                  case "2028":
                    str += "\\L";
                    break;
                  case "2029":
                    str += "\\P";
                    break;
                  default:
                    if (code.substr(0, 2) === "00")
                      str += "\\x" + code.substr(2);
                    else
                      str += json.substr(i, 6);
                }
                i += 5;
                start = i + 1;
              }
              break;
            case "n":
              if (implicitKey || json[i + 2] === '"' || json.length < minMultiLineLength) {
                i += 1;
              } else {
                str += json.slice(start, i) + "\n\n";
                while (json[i + 2] === "\\" && json[i + 3] === "n" && json[i + 4] !== '"') {
                  str += "\n";
                  i += 2;
                }
                str += indent;
                if (json[i + 2] === " ")
                  str += "\\";
                i += 1;
                start = i + 1;
              }
              break;
            default:
              i += 1;
          }
      }
      str = start ? str + json.slice(start) : json;
      return implicitKey ? str : foldFlowLines.foldFlowLines(str, indent, foldFlowLines.FOLD_QUOTED, getFoldOptions(ctx, false));
    }
    function singleQuotedString(value, ctx) {
      if (ctx.options.singleQuote === false || ctx.implicitKey && value.includes("\n") || /[ \t]\n|\n[ \t]/.test(value))
        return doubleQuotedString(value, ctx);
      const indent = ctx.indent || (containsDocumentMarker(value) ? "  " : "");
      const res = "'" + value.replace(/'/g, "''").replace(/\n+/g, `$&
${indent}`) + "'";
      return ctx.implicitKey ? res : foldFlowLines.foldFlowLines(res, indent, foldFlowLines.FOLD_FLOW, getFoldOptions(ctx, false));
    }
    function quotedString(value, ctx) {
      const { singleQuote } = ctx.options;
      let qs;
      if (singleQuote === false)
        qs = doubleQuotedString;
      else {
        const hasDouble = value.includes('"');
        const hasSingle = value.includes("'");
        if (hasDouble && !hasSingle)
          qs = singleQuotedString;
        else if (hasSingle && !hasDouble)
          qs = doubleQuotedString;
        else
          qs = singleQuote ? singleQuotedString : doubleQuotedString;
      }
      return qs(value, ctx);
    }
    var blockEndNewlines;
    try {
      blockEndNewlines = new RegExp("(^|(?<!\n))\n+(?!\n|$)", "g");
    } catch {
      blockEndNewlines = /\n+(?!\n|$)/g;
    }
    function blockString({ comment, type, value }, ctx, onComment, onChompKeep) {
      const { blockQuote, commentString, lineWidth } = ctx.options;
      if (!blockQuote || /\n[\t ]+$/.test(value)) {
        return quotedString(value, ctx);
      }
      const indent = ctx.indent || (ctx.forceBlockIndent || containsDocumentMarker(value) ? "  " : "");
      const literal = blockQuote === "literal" ? true : blockQuote === "folded" || type === Scalar.Scalar.BLOCK_FOLDED ? false : type === Scalar.Scalar.BLOCK_LITERAL ? true : !lineLengthOverLimit(value, lineWidth, indent.length);
      if (!value)
        return literal ? "|\n" : ">\n";
      let chomp;
      let endStart;
      for (endStart = value.length; endStart > 0; --endStart) {
        const ch = value[endStart - 1];
        if (ch !== "\n" && ch !== "	" && ch !== " ")
          break;
      }
      let end = value.substring(endStart);
      const endNlPos = end.indexOf("\n");
      if (endNlPos === -1) {
        chomp = "-";
      } else if (value === end || endNlPos !== end.length - 1) {
        chomp = "+";
        if (onChompKeep)
          onChompKeep();
      } else {
        chomp = "";
      }
      if (end) {
        value = value.slice(0, -end.length);
        if (end[end.length - 1] === "\n")
          end = end.slice(0, -1);
        end = end.replace(blockEndNewlines, `$&${indent}`);
      }
      let startWithSpace = false;
      let startEnd;
      let startNlPos = -1;
      for (startEnd = 0; startEnd < value.length; ++startEnd) {
        const ch = value[startEnd];
        if (ch === " ")
          startWithSpace = true;
        else if (ch === "\n")
          startNlPos = startEnd;
        else
          break;
      }
      let start = value.substring(0, startNlPos < startEnd ? startNlPos + 1 : startEnd);
      if (start) {
        value = value.substring(start.length);
        start = start.replace(/\n+/g, `$&${indent}`);
      }
      const indentSize = indent ? "2" : "1";
      let header = (startWithSpace ? indentSize : "") + chomp;
      if (comment) {
        header += " " + commentString(comment.replace(/ ?[\r\n]+/g, " "));
        if (onComment)
          onComment();
      }
      if (!literal) {
        const foldedValue = value.replace(/\n+/g, "\n$&").replace(/(?:^|\n)([\t ].*)(?:([\n\t ]*)\n(?![\n\t ]))?/g, "$1$2").replace(/\n+/g, `$&${indent}`);
        let literalFallback = false;
        const foldOptions = getFoldOptions(ctx, true);
        if (blockQuote !== "folded" && type !== Scalar.Scalar.BLOCK_FOLDED) {
          foldOptions.onOverflow = () => {
            literalFallback = true;
          };
        }
        const body = foldFlowLines.foldFlowLines(`${start}${foldedValue}${end}`, indent, foldFlowLines.FOLD_BLOCK, foldOptions);
        if (!literalFallback)
          return `>${header}
${indent}${body}`;
      }
      value = value.replace(/\n+/g, `$&${indent}`);
      return `|${header}
${indent}${start}${value}${end}`;
    }
    function plainString(item, ctx, onComment, onChompKeep) {
      const { type, value } = item;
      const { actualString, implicitKey, indent, indentStep, inFlow } = ctx;
      if (implicitKey && value.includes("\n") || inFlow && /[[\]{},]/.test(value)) {
        return quotedString(value, ctx);
      }
      if (/^[\n\t ,[\]{}#&*!|>'"%@`]|^[?-]$|^[?-][ \t]|[\n:][ \t]|[ \t]\n|[\n\t ]#|[\n\t :]$/.test(value)) {
        return implicitKey || inFlow || !value.includes("\n") ? quotedString(value, ctx) : blockString(item, ctx, onComment, onChompKeep);
      }
      if (!implicitKey && !inFlow && type !== Scalar.Scalar.PLAIN && value.includes("\n")) {
        return blockString(item, ctx, onComment, onChompKeep);
      }
      if (containsDocumentMarker(value)) {
        if (indent === "") {
          ctx.forceBlockIndent = true;
          return blockString(item, ctx, onComment, onChompKeep);
        } else if (implicitKey && indent === indentStep) {
          return quotedString(value, ctx);
        }
      }
      const str = value.replace(/\n+/g, `$&
${indent}`);
      if (actualString) {
        const test = (tag) => tag.default && tag.tag !== "tag:yaml.org,2002:str" && tag.test?.test(str);
        const { compat, tags } = ctx.doc.schema;
        if (tags.some(test) || compat?.some(test))
          return quotedString(value, ctx);
      }
      return implicitKey ? str : foldFlowLines.foldFlowLines(str, indent, foldFlowLines.FOLD_FLOW, getFoldOptions(ctx, false));
    }
    function stringifyString(item, ctx, onComment, onChompKeep) {
      const { implicitKey, inFlow } = ctx;
      const ss = typeof item.value === "string" ? item : Object.assign({}, item, { value: String(item.value) });
      let { type } = item;
      if (type !== Scalar.Scalar.QUOTE_DOUBLE) {
        if (/[\x00-\x08\x0b-\x1f\x7f-\x9f\u{D800}-\u{DFFF}]/u.test(ss.value))
          type = Scalar.Scalar.QUOTE_DOUBLE;
      }
      const _stringify = (_type) => {
        switch (_type) {
          case Scalar.Scalar.BLOCK_FOLDED:
          case Scalar.Scalar.BLOCK_LITERAL:
            return implicitKey || inFlow ? quotedString(ss.value, ctx) : blockString(ss, ctx, onComment, onChompKeep);
          case Scalar.Scalar.QUOTE_DOUBLE:
            return doubleQuotedString(ss.value, ctx);
          case Scalar.Scalar.QUOTE_SINGLE:
            return singleQuotedString(ss.value, ctx);
          case Scalar.Scalar.PLAIN:
            return plainString(ss, ctx, onComment, onChompKeep);
          default:
            return null;
        }
      };
      let res = _stringify(type);
      if (res === null) {
        const { defaultKeyType, defaultStringType } = ctx.options;
        const t = implicitKey && defaultKeyType || defaultStringType;
        res = _stringify(t);
        if (res === null)
          throw new Error(`Unsupported default string type ${t}`);
      }
      return res;
    }
    exports.stringifyString = stringifyString;
  }
});

// node_modules/yaml/dist/stringify/stringify.js
var require_stringify = __commonJS({
  "node_modules/yaml/dist/stringify/stringify.js"(exports) {
    "use strict";
    var anchors = require_anchors();
    var identity = require_identity();
    var stringifyComment = require_stringifyComment();
    var stringifyString = require_stringifyString();
    function createStringifyContext(doc, options) {
      const opt = Object.assign({
        blockQuote: true,
        commentString: stringifyComment.stringifyComment,
        defaultKeyType: null,
        defaultStringType: "PLAIN",
        directives: null,
        doubleQuotedAsJSON: false,
        doubleQuotedMinMultiLineLength: 40,
        falseStr: "false",
        flowCollectionPadding: true,
        indentSeq: true,
        lineWidth: 80,
        minContentWidth: 20,
        nullStr: "null",
        simpleKeys: false,
        singleQuote: null,
        trailingComma: false,
        trueStr: "true",
        verifyAliasOrder: true
      }, doc.schema.toStringOptions, options);
      let inFlow;
      switch (opt.collectionStyle) {
        case "block":
          inFlow = false;
          break;
        case "flow":
          inFlow = true;
          break;
        default:
          inFlow = null;
      }
      return {
        anchors: /* @__PURE__ */ new Set(),
        doc,
        flowCollectionPadding: opt.flowCollectionPadding ? " " : "",
        indent: "",
        indentStep: typeof opt.indent === "number" ? " ".repeat(opt.indent) : "  ",
        inFlow,
        options: opt
      };
    }
    function getTagObject(tags, item) {
      if (item.tag) {
        const match = tags.filter((t) => t.tag === item.tag);
        if (match.length > 0)
          return match.find((t) => t.format === item.format) ?? match[0];
      }
      let tagObj = void 0;
      let obj;
      if (identity.isScalar(item)) {
        obj = item.value;
        let match = tags.filter((t) => t.identify?.(obj));
        if (match.length > 1) {
          const testMatch = match.filter((t) => t.test);
          if (testMatch.length > 0)
            match = testMatch;
        }
        tagObj = match.find((t) => t.format === item.format) ?? match.find((t) => !t.format);
      } else {
        obj = item;
        tagObj = tags.find((t) => t.nodeClass && obj instanceof t.nodeClass);
      }
      if (!tagObj) {
        const name = obj?.constructor?.name ?? (obj === null ? "null" : typeof obj);
        throw new Error(`Tag not resolved for ${name} value`);
      }
      return tagObj;
    }
    function stringifyProps(node, tagObj, { anchors: anchors$1, doc }) {
      if (!doc.directives)
        return "";
      const props = [];
      const anchor = (identity.isScalar(node) || identity.isCollection(node)) && node.anchor;
      if (anchor && anchors.anchorIsValid(anchor)) {
        anchors$1.add(anchor);
        props.push(`&${anchor}`);
      }
      const tag = node.tag ?? (tagObj.default ? null : tagObj.tag);
      if (tag)
        props.push(doc.directives.tagString(tag));
      return props.join(" ");
    }
    function stringify(item, ctx, onComment, onChompKeep) {
      if (identity.isPair(item))
        return item.toString(ctx, onComment, onChompKeep);
      if (identity.isAlias(item)) {
        if (ctx.doc.directives)
          return item.toString(ctx);
        if (ctx.resolvedAliases?.has(item)) {
          throw new TypeError(`Cannot stringify circular structure without alias nodes`);
        } else {
          if (ctx.resolvedAliases)
            ctx.resolvedAliases.add(item);
          else
            ctx.resolvedAliases = /* @__PURE__ */ new Set([item]);
          item = item.resolve(ctx.doc);
        }
      }
      let tagObj = void 0;
      const node = identity.isNode(item) ? item : ctx.doc.createNode(item, { onTagObj: (o) => tagObj = o });
      tagObj ?? (tagObj = getTagObject(ctx.doc.schema.tags, node));
      const props = stringifyProps(node, tagObj, ctx);
      if (props.length > 0)
        ctx.indentAtStart = (ctx.indentAtStart ?? 0) + props.length + 1;
      const str = typeof tagObj.stringify === "function" ? tagObj.stringify(node, ctx, onComment, onChompKeep) : identity.isScalar(node) ? stringifyString.stringifyString(node, ctx, onComment, onChompKeep) : node.toString(ctx, onComment, onChompKeep);
      if (!props)
        return str;
      return identity.isScalar(node) || str[0] === "{" || str[0] === "[" ? `${props} ${str}` : `${props}
${ctx.indent}${str}`;
    }
    exports.createStringifyContext = createStringifyContext;
    exports.stringify = stringify;
  }
});

// node_modules/yaml/dist/stringify/stringifyPair.js
var require_stringifyPair = __commonJS({
  "node_modules/yaml/dist/stringify/stringifyPair.js"(exports) {
    "use strict";
    var identity = require_identity();
    var Scalar = require_Scalar();
    var stringify = require_stringify();
    var stringifyComment = require_stringifyComment();
    function stringifyPair({ key, value }, ctx, onComment, onChompKeep) {
      const { allNullValues, doc, indent, indentStep, options: { commentString, indentSeq, simpleKeys } } = ctx;
      let keyComment = identity.isNode(key) && key.comment || null;
      if (simpleKeys) {
        if (keyComment) {
          throw new Error("With simple keys, key nodes cannot have comments");
        }
        if (identity.isCollection(key) || !identity.isNode(key) && typeof key === "object") {
          const msg = "With simple keys, collection cannot be used as a key value";
          throw new Error(msg);
        }
      }
      let explicitKey = !simpleKeys && (!key || keyComment && value == null && !ctx.inFlow || identity.isCollection(key) || (identity.isScalar(key) ? key.type === Scalar.Scalar.BLOCK_FOLDED || key.type === Scalar.Scalar.BLOCK_LITERAL : typeof key === "object"));
      ctx = Object.assign({}, ctx, {
        allNullValues: false,
        implicitKey: !explicitKey && (simpleKeys || !allNullValues),
        indent: indent + indentStep
      });
      let keyCommentDone = false;
      let chompKeep = false;
      let str = stringify.stringify(key, ctx, () => keyCommentDone = true, () => chompKeep = true);
      if (!explicitKey && !ctx.inFlow && str.length > 1024) {
        if (simpleKeys)
          throw new Error("With simple keys, single line scalar must not span more than 1024 characters");
        explicitKey = true;
      }
      if (ctx.inFlow) {
        if (allNullValues || value == null) {
          if (keyCommentDone && onComment)
            onComment();
          return str === "" ? "?" : explicitKey ? `? ${str}` : str;
        }
      } else if (allNullValues && !simpleKeys || value == null && explicitKey) {
        str = `? ${str}`;
        if (keyComment && !keyCommentDone) {
          str += stringifyComment.lineComment(str, ctx.indent, commentString(keyComment));
        } else if (chompKeep && onChompKeep)
          onChompKeep();
        return str;
      }
      if (keyCommentDone)
        keyComment = null;
      if (explicitKey) {
        if (keyComment)
          str += stringifyComment.lineComment(str, ctx.indent, commentString(keyComment));
        str = `? ${str}
${indent}:`;
      } else {
        str = `${str}:`;
        if (keyComment)
          str += stringifyComment.lineComment(str, ctx.indent, commentString(keyComment));
      }
      let vsb, vcb, valueComment;
      if (identity.isNode(value)) {
        vsb = !!value.spaceBefore;
        vcb = value.commentBefore;
        valueComment = value.comment;
      } else {
        vsb = false;
        vcb = null;
        valueComment = null;
        if (value && typeof value === "object")
          value = doc.createNode(value);
      }
      ctx.implicitKey = false;
      if (!explicitKey && !keyComment && identity.isScalar(value))
        ctx.indentAtStart = str.length + 1;
      chompKeep = false;
      if (!indentSeq && indentStep.length >= 2 && !ctx.inFlow && !explicitKey && identity.isSeq(value) && !value.flow && !value.tag && !value.anchor) {
        ctx.indent = ctx.indent.substring(2);
      }
      let valueCommentDone = false;
      const valueStr = stringify.stringify(value, ctx, () => valueCommentDone = true, () => chompKeep = true);
      let ws = " ";
      if (keyComment || vsb || vcb) {
        ws = vsb ? "\n" : "";
        if (vcb) {
          const cs = commentString(vcb);
          ws += `
${stringifyComment.indentComment(cs, ctx.indent)}`;
        }
        if (valueStr === "" && !ctx.inFlow) {
          if (ws === "\n" && valueComment)
            ws = "\n\n";
        } else {
          ws += `
${ctx.indent}`;
        }
      } else if (!explicitKey && identity.isCollection(value)) {
        const vs0 = valueStr[0];
        const nl0 = valueStr.indexOf("\n");
        const hasNewline = nl0 !== -1;
        const flow = ctx.inFlow ?? value.flow ?? value.items.length === 0;
        if (hasNewline || !flow) {
          let hasPropsLine = false;
          if (hasNewline && (vs0 === "&" || vs0 === "!")) {
            let sp0 = valueStr.indexOf(" ");
            if (vs0 === "&" && sp0 !== -1 && sp0 < nl0 && valueStr[sp0 + 1] === "!") {
              sp0 = valueStr.indexOf(" ", sp0 + 1);
            }
            if (sp0 === -1 || nl0 < sp0)
              hasPropsLine = true;
          }
          if (!hasPropsLine)
            ws = `
${ctx.indent}`;
        }
      } else if (valueStr === "" || valueStr[0] === "\n") {
        ws = "";
      }
      str += ws + valueStr;
      if (ctx.inFlow) {
        if (valueCommentDone && onComment)
          onComment();
      } else if (valueComment && !valueCommentDone) {
        str += stringifyComment.lineComment(str, ctx.indent, commentString(valueComment));
      } else if (chompKeep && onChompKeep) {
        onChompKeep();
      }
      return str;
    }
    exports.stringifyPair = stringifyPair;
  }
});

// node_modules/yaml/dist/log.js
var require_log = __commonJS({
  "node_modules/yaml/dist/log.js"(exports) {
    "use strict";
    var node_process = __require("process");
    function debug(logLevel, ...messages) {
      if (logLevel === "debug")
        console.log(...messages);
    }
    function warn(logLevel, warning) {
      if (logLevel === "debug" || logLevel === "warn") {
        if (typeof node_process.emitWarning === "function")
          node_process.emitWarning(warning);
        else
          console.warn(warning);
      }
    }
    exports.debug = debug;
    exports.warn = warn;
  }
});

// node_modules/yaml/dist/schema/yaml-1.1/merge.js
var require_merge = __commonJS({
  "node_modules/yaml/dist/schema/yaml-1.1/merge.js"(exports) {
    "use strict";
    var identity = require_identity();
    var Scalar = require_Scalar();
    var MERGE_KEY = "<<";
    var merge = {
      identify: (value) => value === MERGE_KEY || typeof value === "symbol" && value.description === MERGE_KEY,
      default: "key",
      tag: "tag:yaml.org,2002:merge",
      test: /^<<$/,
      resolve: () => Object.assign(new Scalar.Scalar(Symbol(MERGE_KEY)), {
        addToJSMap: addMergeToJSMap
      }),
      stringify: () => MERGE_KEY
    };
    var isMergeKey = (ctx, key) => (merge.identify(key) || identity.isScalar(key) && (!key.type || key.type === Scalar.Scalar.PLAIN) && merge.identify(key.value)) && ctx?.doc.schema.tags.some((tag) => tag.tag === merge.tag && tag.default);
    function addMergeToJSMap(ctx, map, value) {
      const source = resolveAliasValue(ctx, value);
      if (identity.isSeq(source))
        for (const it of source.items)
          mergeValue(ctx, map, it);
      else if (Array.isArray(source))
        for (const it of source)
          mergeValue(ctx, map, it);
      else
        mergeValue(ctx, map, source);
    }
    function mergeValue(ctx, map, value) {
      const source = resolveAliasValue(ctx, value);
      if (!identity.isMap(source))
        throw new Error("Merge sources must be maps or map aliases");
      const srcMap = source.toJSON(null, ctx, Map);
      for (const [key, value2] of srcMap) {
        if (map instanceof Map) {
          if (!map.has(key))
            map.set(key, value2);
        } else if (map instanceof Set) {
          map.add(key);
        } else if (!Object.prototype.hasOwnProperty.call(map, key)) {
          Object.defineProperty(map, key, {
            value: value2,
            writable: true,
            enumerable: true,
            configurable: true
          });
        }
      }
      return map;
    }
    function resolveAliasValue(ctx, value) {
      return ctx && identity.isAlias(value) ? value.resolve(ctx.doc, ctx) : value;
    }
    exports.addMergeToJSMap = addMergeToJSMap;
    exports.isMergeKey = isMergeKey;
    exports.merge = merge;
  }
});

// node_modules/yaml/dist/nodes/addPairToJSMap.js
var require_addPairToJSMap = __commonJS({
  "node_modules/yaml/dist/nodes/addPairToJSMap.js"(exports) {
    "use strict";
    var log = require_log();
    var merge = require_merge();
    var stringify = require_stringify();
    var identity = require_identity();
    var toJS = require_toJS();
    function addPairToJSMap(ctx, map, { key, value }) {
      if (identity.isNode(key) && key.addToJSMap)
        key.addToJSMap(ctx, map, value);
      else if (merge.isMergeKey(ctx, key))
        merge.addMergeToJSMap(ctx, map, value);
      else {
        const jsKey = toJS.toJS(key, "", ctx);
        if (map instanceof Map) {
          map.set(jsKey, toJS.toJS(value, jsKey, ctx));
        } else if (map instanceof Set) {
          map.add(jsKey);
        } else {
          const stringKey = stringifyKey(key, jsKey, ctx);
          const jsValue = toJS.toJS(value, stringKey, ctx);
          if (stringKey in map)
            Object.defineProperty(map, stringKey, {
              value: jsValue,
              writable: true,
              enumerable: true,
              configurable: true
            });
          else
            map[stringKey] = jsValue;
        }
      }
      return map;
    }
    function stringifyKey(key, jsKey, ctx) {
      if (jsKey === null)
        return "";
      if (typeof jsKey !== "object")
        return String(jsKey);
      if (identity.isNode(key) && ctx?.doc) {
        const strCtx = stringify.createStringifyContext(ctx.doc, {});
        strCtx.anchors = /* @__PURE__ */ new Set();
        for (const node of ctx.anchors.keys())
          strCtx.anchors.add(node.anchor);
        strCtx.inFlow = true;
        strCtx.inStringifyKey = true;
        const strKey = key.toString(strCtx);
        if (!ctx.mapKeyWarned) {
          let jsonStr = JSON.stringify(strKey);
          if (jsonStr.length > 40)
            jsonStr = jsonStr.substring(0, 36) + '..."';
          log.warn(ctx.doc.options.logLevel, `Keys with collection values will be stringified due to JS Object restrictions: ${jsonStr}. Set mapAsMap: true to use object keys.`);
          ctx.mapKeyWarned = true;
        }
        return strKey;
      }
      return JSON.stringify(jsKey);
    }
    exports.addPairToJSMap = addPairToJSMap;
  }
});

// node_modules/yaml/dist/nodes/Pair.js
var require_Pair = __commonJS({
  "node_modules/yaml/dist/nodes/Pair.js"(exports) {
    "use strict";
    var createNode = require_createNode();
    var stringifyPair = require_stringifyPair();
    var addPairToJSMap = require_addPairToJSMap();
    var identity = require_identity();
    function createPair(key, value, ctx) {
      const k = createNode.createNode(key, void 0, ctx);
      const v = createNode.createNode(value, void 0, ctx);
      return new Pair(k, v);
    }
    var Pair = class _Pair {
      constructor(key, value = null) {
        Object.defineProperty(this, identity.NODE_TYPE, { value: identity.PAIR });
        this.key = key;
        this.value = value;
      }
      clone(schema) {
        let { key, value } = this;
        if (identity.isNode(key))
          key = key.clone(schema);
        if (identity.isNode(value))
          value = value.clone(schema);
        return new _Pair(key, value);
      }
      toJSON(_, ctx) {
        const pair = ctx?.mapAsMap ? /* @__PURE__ */ new Map() : {};
        return addPairToJSMap.addPairToJSMap(ctx, pair, this);
      }
      toString(ctx, onComment, onChompKeep) {
        return ctx?.doc ? stringifyPair.stringifyPair(this, ctx, onComment, onChompKeep) : JSON.stringify(this);
      }
    };
    exports.Pair = Pair;
    exports.createPair = createPair;
  }
});

// node_modules/yaml/dist/stringify/stringifyCollection.js
var require_stringifyCollection = __commonJS({
  "node_modules/yaml/dist/stringify/stringifyCollection.js"(exports) {
    "use strict";
    var identity = require_identity();
    var stringify = require_stringify();
    var stringifyComment = require_stringifyComment();
    function stringifyCollection(collection, ctx, options) {
      const flow = ctx.inFlow ?? collection.flow;
      const stringify2 = flow ? stringifyFlowCollection : stringifyBlockCollection;
      return stringify2(collection, ctx, options);
    }
    function stringifyBlockCollection({ comment, items }, ctx, { blockItemPrefix, flowChars, itemIndent, onChompKeep, onComment }) {
      const { indent, options: { commentString } } = ctx;
      const itemCtx = Object.assign({}, ctx, { indent: itemIndent, type: null });
      let chompKeep = false;
      const lines = [];
      for (let i = 0; i < items.length; ++i) {
        const item = items[i];
        let comment2 = null;
        if (identity.isNode(item)) {
          if (!chompKeep && item.spaceBefore)
            lines.push("");
          addCommentBefore(ctx, lines, item.commentBefore, chompKeep);
          if (item.comment)
            comment2 = item.comment;
        } else if (identity.isPair(item)) {
          const ik = identity.isNode(item.key) ? item.key : null;
          if (ik) {
            if (!chompKeep && ik.spaceBefore)
              lines.push("");
            addCommentBefore(ctx, lines, ik.commentBefore, chompKeep);
          }
        }
        chompKeep = false;
        let str2 = stringify.stringify(item, itemCtx, () => comment2 = null, () => chompKeep = true);
        if (comment2)
          str2 += stringifyComment.lineComment(str2, itemIndent, commentString(comment2));
        if (chompKeep && comment2)
          chompKeep = false;
        lines.push(blockItemPrefix + str2);
      }
      let str;
      if (lines.length === 0) {
        str = flowChars.start + flowChars.end;
      } else {
        str = lines[0];
        for (let i = 1; i < lines.length; ++i) {
          const line = lines[i];
          str += line ? `
${indent}${line}` : "\n";
        }
      }
      if (comment) {
        str += "\n" + stringifyComment.indentComment(commentString(comment), indent);
        if (onComment)
          onComment();
      } else if (chompKeep && onChompKeep)
        onChompKeep();
      return str;
    }
    function stringifyFlowCollection({ items }, ctx, { flowChars, itemIndent }) {
      const { indent, indentStep, flowCollectionPadding: fcPadding, options: { commentString } } = ctx;
      itemIndent += indentStep;
      const itemCtx = Object.assign({}, ctx, {
        indent: itemIndent,
        inFlow: true,
        type: null
      });
      let reqNewline = false;
      let linesAtValue = 0;
      const lines = [];
      for (let i = 0; i < items.length; ++i) {
        const item = items[i];
        let comment = null;
        if (identity.isNode(item)) {
          if (item.spaceBefore)
            lines.push("");
          addCommentBefore(ctx, lines, item.commentBefore, false);
          if (item.comment)
            comment = item.comment;
        } else if (identity.isPair(item)) {
          const ik = identity.isNode(item.key) ? item.key : null;
          if (ik) {
            if (ik.spaceBefore)
              lines.push("");
            addCommentBefore(ctx, lines, ik.commentBefore, false);
            if (ik.comment)
              reqNewline = true;
          }
          const iv = identity.isNode(item.value) ? item.value : null;
          if (iv) {
            if (iv.comment)
              comment = iv.comment;
            if (iv.commentBefore)
              reqNewline = true;
          } else if (item.value == null && ik?.comment) {
            comment = ik.comment;
          }
        }
        if (comment)
          reqNewline = true;
        let str = stringify.stringify(item, itemCtx, () => comment = null);
        reqNewline || (reqNewline = lines.length > linesAtValue || str.includes("\n"));
        if (i < items.length - 1) {
          str += ",";
        } else if (ctx.options.trailingComma) {
          if (ctx.options.lineWidth > 0) {
            reqNewline || (reqNewline = lines.reduce((sum, line) => sum + line.length + 2, 2) + (str.length + 2) > ctx.options.lineWidth);
          }
          if (reqNewline) {
            str += ",";
          }
        }
        if (comment)
          str += stringifyComment.lineComment(str, itemIndent, commentString(comment));
        lines.push(str);
        linesAtValue = lines.length;
      }
      const { start, end } = flowChars;
      if (lines.length === 0) {
        return start + end;
      } else {
        if (!reqNewline) {
          const len = lines.reduce((sum, line) => sum + line.length + 2, 2);
          reqNewline = ctx.options.lineWidth > 0 && len > ctx.options.lineWidth;
        }
        if (reqNewline) {
          let str = start;
          for (const line of lines)
            str += line ? `
${indentStep}${indent}${line}` : "\n";
          return `${str}
${indent}${end}`;
        } else {
          return `${start}${fcPadding}${lines.join(" ")}${fcPadding}${end}`;
        }
      }
    }
    function addCommentBefore({ indent, options: { commentString } }, lines, comment, chompKeep) {
      if (comment && chompKeep)
        comment = comment.replace(/^\n+/, "");
      if (comment) {
        const ic = stringifyComment.indentComment(commentString(comment), indent);
        lines.push(ic.trimStart());
      }
    }
    exports.stringifyCollection = stringifyCollection;
  }
});

// node_modules/yaml/dist/nodes/YAMLMap.js
var require_YAMLMap = __commonJS({
  "node_modules/yaml/dist/nodes/YAMLMap.js"(exports) {
    "use strict";
    var stringifyCollection = require_stringifyCollection();
    var addPairToJSMap = require_addPairToJSMap();
    var Collection = require_Collection();
    var identity = require_identity();
    var Pair = require_Pair();
    var Scalar = require_Scalar();
    function findPair(items, key) {
      const k = identity.isScalar(key) ? key.value : key;
      for (const it of items) {
        if (identity.isPair(it)) {
          if (it.key === key || it.key === k)
            return it;
          if (identity.isScalar(it.key) && it.key.value === k)
            return it;
        }
      }
      return void 0;
    }
    var YAMLMap = class extends Collection.Collection {
      static get tagName() {
        return "tag:yaml.org,2002:map";
      }
      constructor(schema) {
        super(identity.MAP, schema);
        this.items = [];
      }
      /**
       * A generic collection parsing method that can be extended
       * to other node classes that inherit from YAMLMap
       */
      static from(schema, obj, ctx) {
        const { keepUndefined, replacer } = ctx;
        const map = new this(schema);
        const add = (key, value) => {
          if (typeof replacer === "function")
            value = replacer.call(obj, key, value);
          else if (Array.isArray(replacer) && !replacer.includes(key))
            return;
          if (value !== void 0 || keepUndefined)
            map.items.push(Pair.createPair(key, value, ctx));
        };
        if (obj instanceof Map) {
          for (const [key, value] of obj)
            add(key, value);
        } else if (obj && typeof obj === "object") {
          for (const key of Object.keys(obj))
            add(key, obj[key]);
        }
        if (typeof schema.sortMapEntries === "function") {
          map.items.sort(schema.sortMapEntries);
        }
        return map;
      }
      /**
       * Adds a value to the collection.
       *
       * @param overwrite - If not set `true`, using a key that is already in the
       *   collection will throw. Otherwise, overwrites the previous value.
       */
      add(pair, overwrite) {
        let _pair;
        if (identity.isPair(pair))
          _pair = pair;
        else if (!pair || typeof pair !== "object" || !("key" in pair)) {
          _pair = new Pair.Pair(pair, pair?.value);
        } else
          _pair = new Pair.Pair(pair.key, pair.value);
        const prev = findPair(this.items, _pair.key);
        const sortEntries = this.schema?.sortMapEntries;
        if (prev) {
          if (!overwrite)
            throw new Error(`Key ${_pair.key} already set`);
          if (identity.isScalar(prev.value) && Scalar.isScalarValue(_pair.value))
            prev.value.value = _pair.value;
          else
            prev.value = _pair.value;
        } else if (sortEntries) {
          const i = this.items.findIndex((item) => sortEntries(_pair, item) < 0);
          if (i === -1)
            this.items.push(_pair);
          else
            this.items.splice(i, 0, _pair);
        } else {
          this.items.push(_pair);
        }
      }
      delete(key) {
        const it = findPair(this.items, key);
        if (!it)
          return false;
        const del = this.items.splice(this.items.indexOf(it), 1);
        return del.length > 0;
      }
      get(key, keepScalar) {
        const it = findPair(this.items, key);
        const node = it?.value;
        return (!keepScalar && identity.isScalar(node) ? node.value : node) ?? void 0;
      }
      has(key) {
        return !!findPair(this.items, key);
      }
      set(key, value) {
        this.add(new Pair.Pair(key, value), true);
      }
      /**
       * @param ctx - Conversion context, originally set in Document#toJS()
       * @param {Class} Type - If set, forces the returned collection type
       * @returns Instance of Type, Map, or Object
       */
      toJSON(_, ctx, Type) {
        const map = Type ? new Type() : ctx?.mapAsMap ? /* @__PURE__ */ new Map() : {};
        if (ctx?.onCreate)
          ctx.onCreate(map);
        for (const item of this.items)
          addPairToJSMap.addPairToJSMap(ctx, map, item);
        return map;
      }
      toString(ctx, onComment, onChompKeep) {
        if (!ctx)
          return JSON.stringify(this);
        for (const item of this.items) {
          if (!identity.isPair(item))
            throw new Error(`Map items must all be pairs; found ${JSON.stringify(item)} instead`);
        }
        if (!ctx.allNullValues && this.hasAllNullValues(false))
          ctx = Object.assign({}, ctx, { allNullValues: true });
        return stringifyCollection.stringifyCollection(this, ctx, {
          blockItemPrefix: "",
          flowChars: { start: "{", end: "}" },
          itemIndent: ctx.indent || "",
          onChompKeep,
          onComment
        });
      }
    };
    exports.YAMLMap = YAMLMap;
    exports.findPair = findPair;
  }
});

// node_modules/yaml/dist/schema/common/map.js
var require_map = __commonJS({
  "node_modules/yaml/dist/schema/common/map.js"(exports) {
    "use strict";
    var identity = require_identity();
    var YAMLMap = require_YAMLMap();
    var map = {
      collection: "map",
      default: true,
      nodeClass: YAMLMap.YAMLMap,
      tag: "tag:yaml.org,2002:map",
      resolve(map2, onError) {
        if (!identity.isMap(map2))
          onError("Expected a mapping for this tag");
        return map2;
      },
      createNode: (schema, obj, ctx) => YAMLMap.YAMLMap.from(schema, obj, ctx)
    };
    exports.map = map;
  }
});

// node_modules/yaml/dist/nodes/YAMLSeq.js
var require_YAMLSeq = __commonJS({
  "node_modules/yaml/dist/nodes/YAMLSeq.js"(exports) {
    "use strict";
    var createNode = require_createNode();
    var stringifyCollection = require_stringifyCollection();
    var Collection = require_Collection();
    var identity = require_identity();
    var Scalar = require_Scalar();
    var toJS = require_toJS();
    var YAMLSeq = class extends Collection.Collection {
      static get tagName() {
        return "tag:yaml.org,2002:seq";
      }
      constructor(schema) {
        super(identity.SEQ, schema);
        this.items = [];
      }
      add(value) {
        this.items.push(value);
      }
      /**
       * Removes a value from the collection.
       *
       * `key` must contain a representation of an integer for this to succeed.
       * It may be wrapped in a `Scalar`.
       *
       * @returns `true` if the item was found and removed.
       */
      delete(key) {
        const idx = asItemIndex(key);
        if (typeof idx !== "number")
          return false;
        const del = this.items.splice(idx, 1);
        return del.length > 0;
      }
      get(key, keepScalar) {
        const idx = asItemIndex(key);
        if (typeof idx !== "number")
          return void 0;
        const it = this.items[idx];
        return !keepScalar && identity.isScalar(it) ? it.value : it;
      }
      /**
       * Checks if the collection includes a value with the key `key`.
       *
       * `key` must contain a representation of an integer for this to succeed.
       * It may be wrapped in a `Scalar`.
       */
      has(key) {
        const idx = asItemIndex(key);
        return typeof idx === "number" && idx < this.items.length;
      }
      /**
       * Sets a value in this collection. For `!!set`, `value` needs to be a
       * boolean to add/remove the item from the set.
       *
       * If `key` does not contain a representation of an integer, this will throw.
       * It may be wrapped in a `Scalar`.
       */
      set(key, value) {
        const idx = asItemIndex(key);
        if (typeof idx !== "number")
          throw new Error(`Expected a valid index, not ${key}.`);
        const prev = this.items[idx];
        if (identity.isScalar(prev) && Scalar.isScalarValue(value))
          prev.value = value;
        else
          this.items[idx] = value;
      }
      toJSON(_, ctx) {
        const seq = [];
        if (ctx?.onCreate)
          ctx.onCreate(seq);
        let i = 0;
        for (const item of this.items)
          seq.push(toJS.toJS(item, String(i++), ctx));
        return seq;
      }
      toString(ctx, onComment, onChompKeep) {
        if (!ctx)
          return JSON.stringify(this);
        return stringifyCollection.stringifyCollection(this, ctx, {
          blockItemPrefix: "- ",
          flowChars: { start: "[", end: "]" },
          itemIndent: (ctx.indent || "") + "  ",
          onChompKeep,
          onComment
        });
      }
      static from(schema, obj, ctx) {
        const { replacer } = ctx;
        const seq = new this(schema);
        if (obj && Symbol.iterator in Object(obj)) {
          let i = 0;
          for (let it of obj) {
            if (typeof replacer === "function") {
              const key = obj instanceof Set ? it : String(i++);
              it = replacer.call(obj, key, it);
            }
            seq.items.push(createNode.createNode(it, void 0, ctx));
          }
        }
        return seq;
      }
    };
    function asItemIndex(key) {
      let idx = identity.isScalar(key) ? key.value : key;
      if (idx && typeof idx === "string")
        idx = Number(idx);
      return typeof idx === "number" && Number.isInteger(idx) && idx >= 0 ? idx : null;
    }
    exports.YAMLSeq = YAMLSeq;
  }
});

// node_modules/yaml/dist/schema/common/seq.js
var require_seq = __commonJS({
  "node_modules/yaml/dist/schema/common/seq.js"(exports) {
    "use strict";
    var identity = require_identity();
    var YAMLSeq = require_YAMLSeq();
    var seq = {
      collection: "seq",
      default: true,
      nodeClass: YAMLSeq.YAMLSeq,
      tag: "tag:yaml.org,2002:seq",
      resolve(seq2, onError) {
        if (!identity.isSeq(seq2))
          onError("Expected a sequence for this tag");
        return seq2;
      },
      createNode: (schema, obj, ctx) => YAMLSeq.YAMLSeq.from(schema, obj, ctx)
    };
    exports.seq = seq;
  }
});

// node_modules/yaml/dist/schema/common/string.js
var require_string = __commonJS({
  "node_modules/yaml/dist/schema/common/string.js"(exports) {
    "use strict";
    var stringifyString = require_stringifyString();
    var string = {
      identify: (value) => typeof value === "string",
      default: true,
      tag: "tag:yaml.org,2002:str",
      resolve: (str) => str,
      stringify(item, ctx, onComment, onChompKeep) {
        ctx = Object.assign({ actualString: true }, ctx);
        return stringifyString.stringifyString(item, ctx, onComment, onChompKeep);
      }
    };
    exports.string = string;
  }
});

// node_modules/yaml/dist/schema/common/null.js
var require_null = __commonJS({
  "node_modules/yaml/dist/schema/common/null.js"(exports) {
    "use strict";
    var Scalar = require_Scalar();
    var nullTag = {
      identify: (value) => value == null,
      createNode: () => new Scalar.Scalar(null),
      default: true,
      tag: "tag:yaml.org,2002:null",
      test: /^(?:~|[Nn]ull|NULL)?$/,
      resolve: () => new Scalar.Scalar(null),
      stringify: ({ source }, ctx) => typeof source === "string" && nullTag.test.test(source) ? source : ctx.options.nullStr
    };
    exports.nullTag = nullTag;
  }
});

// node_modules/yaml/dist/schema/core/bool.js
var require_bool = __commonJS({
  "node_modules/yaml/dist/schema/core/bool.js"(exports) {
    "use strict";
    var Scalar = require_Scalar();
    var boolTag = {
      identify: (value) => typeof value === "boolean",
      default: true,
      tag: "tag:yaml.org,2002:bool",
      test: /^(?:[Tt]rue|TRUE|[Ff]alse|FALSE)$/,
      resolve: (str) => new Scalar.Scalar(str[0] === "t" || str[0] === "T"),
      stringify({ source, value }, ctx) {
        if (source && boolTag.test.test(source)) {
          const sv = source[0] === "t" || source[0] === "T";
          if (value === sv)
            return source;
        }
        return value ? ctx.options.trueStr : ctx.options.falseStr;
      }
    };
    exports.boolTag = boolTag;
  }
});

// node_modules/yaml/dist/stringify/stringifyNumber.js
var require_stringifyNumber = __commonJS({
  "node_modules/yaml/dist/stringify/stringifyNumber.js"(exports) {
    "use strict";
    function stringifyNumber({ format, minFractionDigits, tag, value }) {
      if (typeof value === "bigint")
        return String(value);
      const num = typeof value === "number" ? value : Number(value);
      if (!isFinite(num))
        return isNaN(num) ? ".nan" : num < 0 ? "-.inf" : ".inf";
      let n = Object.is(value, -0) ? "-0" : JSON.stringify(value);
      if (!format && minFractionDigits && (!tag || tag === "tag:yaml.org,2002:float") && /^-?\d/.test(n) && !n.includes("e")) {
        let i = n.indexOf(".");
        if (i < 0) {
          i = n.length;
          n += ".";
        }
        let d = minFractionDigits - (n.length - i - 1);
        while (d-- > 0)
          n += "0";
      }
      return n;
    }
    exports.stringifyNumber = stringifyNumber;
  }
});

// node_modules/yaml/dist/schema/core/float.js
var require_float = __commonJS({
  "node_modules/yaml/dist/schema/core/float.js"(exports) {
    "use strict";
    var Scalar = require_Scalar();
    var stringifyNumber = require_stringifyNumber();
    var floatNaN = {
      identify: (value) => typeof value === "number",
      default: true,
      tag: "tag:yaml.org,2002:float",
      test: /^(?:[-+]?\.(?:inf|Inf|INF)|\.nan|\.NaN|\.NAN)$/,
      resolve: (str) => str.slice(-3).toLowerCase() === "nan" ? NaN : str[0] === "-" ? Number.NEGATIVE_INFINITY : Number.POSITIVE_INFINITY,
      stringify: stringifyNumber.stringifyNumber
    };
    var floatExp = {
      identify: (value) => typeof value === "number",
      default: true,
      tag: "tag:yaml.org,2002:float",
      format: "EXP",
      test: /^[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)[eE][-+]?[0-9]+$/,
      resolve: (str) => parseFloat(str),
      stringify(node) {
        const num = Number(node.value);
        return isFinite(num) ? num.toExponential() : stringifyNumber.stringifyNumber(node);
      }
    };
    var float = {
      identify: (value) => typeof value === "number",
      default: true,
      tag: "tag:yaml.org,2002:float",
      test: /^[-+]?(?:\.[0-9]+|[0-9]+\.[0-9]*)$/,
      resolve(str) {
        const node = new Scalar.Scalar(parseFloat(str));
        const dot = str.indexOf(".");
        if (dot !== -1 && str[str.length - 1] === "0")
          node.minFractionDigits = str.length - dot - 1;
        return node;
      },
      stringify: stringifyNumber.stringifyNumber
    };
    exports.float = float;
    exports.floatExp = floatExp;
    exports.floatNaN = floatNaN;
  }
});

// node_modules/yaml/dist/schema/core/int.js
var require_int = __commonJS({
  "node_modules/yaml/dist/schema/core/int.js"(exports) {
    "use strict";
    var stringifyNumber = require_stringifyNumber();
    var intIdentify = (value) => typeof value === "bigint" || Number.isInteger(value);
    var intResolve = (str, offset, radix, { intAsBigInt }) => intAsBigInt ? BigInt(str) : parseInt(str.substring(offset), radix);
    function intStringify(node, radix, prefix) {
      const { value } = node;
      if (intIdentify(value) && value >= 0)
        return prefix + value.toString(radix);
      return stringifyNumber.stringifyNumber(node);
    }
    var intOct = {
      identify: (value) => intIdentify(value) && value >= 0,
      default: true,
      tag: "tag:yaml.org,2002:int",
      format: "OCT",
      test: /^0o[0-7]+$/,
      resolve: (str, _onError, opt) => intResolve(str, 2, 8, opt),
      stringify: (node) => intStringify(node, 8, "0o")
    };
    var int = {
      identify: intIdentify,
      default: true,
      tag: "tag:yaml.org,2002:int",
      test: /^[-+]?[0-9]+$/,
      resolve: (str, _onError, opt) => intResolve(str, 0, 10, opt),
      stringify: stringifyNumber.stringifyNumber
    };
    var intHex = {
      identify: (value) => intIdentify(value) && value >= 0,
      default: true,
      tag: "tag:yaml.org,2002:int",
      format: "HEX",
      test: /^0x[0-9a-fA-F]+$/,
      resolve: (str, _onError, opt) => intResolve(str, 2, 16, opt),
      stringify: (node) => intStringify(node, 16, "0x")
    };
    exports.int = int;
    exports.intHex = intHex;
    exports.intOct = intOct;
  }
});

// node_modules/yaml/dist/schema/core/schema.js
var require_schema = __commonJS({
  "node_modules/yaml/dist/schema/core/schema.js"(exports) {
    "use strict";
    var map = require_map();
    var _null = require_null();
    var seq = require_seq();
    var string = require_string();
    var bool2 = require_bool();
    var float = require_float();
    var int = require_int();
    var schema = [
      map.map,
      seq.seq,
      string.string,
      _null.nullTag,
      bool2.boolTag,
      int.intOct,
      int.int,
      int.intHex,
      float.floatNaN,
      float.floatExp,
      float.float
    ];
    exports.schema = schema;
  }
});

// node_modules/yaml/dist/schema/json/schema.js
var require_schema2 = __commonJS({
  "node_modules/yaml/dist/schema/json/schema.js"(exports) {
    "use strict";
    var Scalar = require_Scalar();
    var map = require_map();
    var seq = require_seq();
    function intIdentify(value) {
      return typeof value === "bigint" || Number.isInteger(value);
    }
    var stringifyJSON = ({ value }) => JSON.stringify(value);
    var jsonScalars = [
      {
        identify: (value) => typeof value === "string",
        default: true,
        tag: "tag:yaml.org,2002:str",
        resolve: (str) => str,
        stringify: stringifyJSON
      },
      {
        identify: (value) => value == null,
        createNode: () => new Scalar.Scalar(null),
        default: true,
        tag: "tag:yaml.org,2002:null",
        test: /^null$/,
        resolve: () => null,
        stringify: stringifyJSON
      },
      {
        identify: (value) => typeof value === "boolean",
        default: true,
        tag: "tag:yaml.org,2002:bool",
        test: /^true$|^false$/,
        resolve: (str) => str === "true",
        stringify: stringifyJSON
      },
      {
        identify: intIdentify,
        default: true,
        tag: "tag:yaml.org,2002:int",
        test: /^-?(?:0|[1-9][0-9]*)$/,
        resolve: (str, _onError, { intAsBigInt }) => intAsBigInt ? BigInt(str) : parseInt(str, 10),
        stringify: ({ value }) => intIdentify(value) ? value.toString() : JSON.stringify(value)
      },
      {
        identify: (value) => typeof value === "number",
        default: true,
        tag: "tag:yaml.org,2002:float",
        test: /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*)?(?:[eE][-+]?[0-9]+)?$/,
        resolve: (str) => parseFloat(str),
        stringify: stringifyJSON
      }
    ];
    var jsonError = {
      default: true,
      tag: "",
      test: /^/,
      resolve(str, onError) {
        onError(`Unresolved plain scalar ${JSON.stringify(str)}`);
        return str;
      }
    };
    var schema = [map.map, seq.seq].concat(jsonScalars, jsonError);
    exports.schema = schema;
  }
});

// node_modules/yaml/dist/schema/yaml-1.1/binary.js
var require_binary = __commonJS({
  "node_modules/yaml/dist/schema/yaml-1.1/binary.js"(exports) {
    "use strict";
    var node_buffer = __require("buffer");
    var Scalar = require_Scalar();
    var stringifyString = require_stringifyString();
    var binary = {
      identify: (value) => value instanceof Uint8Array,
      // Buffer inherits from Uint8Array
      default: false,
      tag: "tag:yaml.org,2002:binary",
      /**
       * Returns a Buffer in node and an Uint8Array in browsers
       *
       * To use the resulting buffer as an image, you'll want to do something like:
       *
       *   const blob = new Blob([buffer], { type: 'image/jpeg' })
       *   document.querySelector('#photo').src = URL.createObjectURL(blob)
       */
      resolve(src, onError) {
        if (typeof node_buffer.Buffer === "function") {
          return node_buffer.Buffer.from(src, "base64");
        } else if (typeof atob === "function") {
          const str = atob(src.replace(/[\n\r]/g, ""));
          const buffer = new Uint8Array(str.length);
          for (let i = 0; i < str.length; ++i)
            buffer[i] = str.charCodeAt(i);
          return buffer;
        } else {
          onError("This environment does not support reading binary tags; either Buffer or atob is required");
          return src;
        }
      },
      stringify({ comment, type, value }, ctx, onComment, onChompKeep) {
        if (!value)
          return "";
        const buf = value;
        let str;
        if (typeof node_buffer.Buffer === "function") {
          str = buf instanceof node_buffer.Buffer ? buf.toString("base64") : node_buffer.Buffer.from(buf.buffer).toString("base64");
        } else if (typeof btoa === "function") {
          let s = "";
          for (let i = 0; i < buf.length; ++i)
            s += String.fromCharCode(buf[i]);
          str = btoa(s);
        } else {
          throw new Error("This environment does not support writing binary tags; either Buffer or btoa is required");
        }
        type ?? (type = Scalar.Scalar.BLOCK_LITERAL);
        if (type !== Scalar.Scalar.QUOTE_DOUBLE) {
          const lineWidth = Math.max(ctx.options.lineWidth - ctx.indent.length, ctx.options.minContentWidth);
          const n = Math.ceil(str.length / lineWidth);
          const lines = new Array(n);
          for (let i = 0, o = 0; i < n; ++i, o += lineWidth) {
            lines[i] = str.substr(o, lineWidth);
          }
          str = lines.join(type === Scalar.Scalar.BLOCK_LITERAL ? "\n" : " ");
        }
        return stringifyString.stringifyString({ comment, type, value: str }, ctx, onComment, onChompKeep);
      }
    };
    exports.binary = binary;
  }
});

// node_modules/yaml/dist/schema/yaml-1.1/pairs.js
var require_pairs = __commonJS({
  "node_modules/yaml/dist/schema/yaml-1.1/pairs.js"(exports) {
    "use strict";
    var identity = require_identity();
    var Pair = require_Pair();
    var Scalar = require_Scalar();
    var YAMLSeq = require_YAMLSeq();
    function resolvePairs(seq, onError) {
      if (identity.isSeq(seq)) {
        for (let i = 0; i < seq.items.length; ++i) {
          let item = seq.items[i];
          if (identity.isPair(item))
            continue;
          else if (identity.isMap(item)) {
            if (item.items.length > 1)
              onError("Each pair must have its own sequence indicator");
            const pair = item.items[0] || new Pair.Pair(new Scalar.Scalar(null));
            if (item.commentBefore)
              pair.key.commentBefore = pair.key.commentBefore ? `${item.commentBefore}
${pair.key.commentBefore}` : item.commentBefore;
            if (item.comment) {
              const cn = pair.value ?? pair.key;
              cn.comment = cn.comment ? `${item.comment}
${cn.comment}` : item.comment;
            }
            item = pair;
          }
          seq.items[i] = identity.isPair(item) ? item : new Pair.Pair(item);
        }
      } else
        onError("Expected a sequence for this tag");
      return seq;
    }
    function createPairs(schema, iterable, ctx) {
      const { replacer } = ctx;
      const pairs2 = new YAMLSeq.YAMLSeq(schema);
      pairs2.tag = "tag:yaml.org,2002:pairs";
      let i = 0;
      if (iterable && Symbol.iterator in Object(iterable))
        for (let it of iterable) {
          if (typeof replacer === "function")
            it = replacer.call(iterable, String(i++), it);
          let key, value;
          if (Array.isArray(it)) {
            if (it.length === 2) {
              key = it[0];
              value = it[1];
            } else
              throw new TypeError(`Expected [key, value] tuple: ${it}`);
          } else if (it && it instanceof Object) {
            const keys = Object.keys(it);
            if (keys.length === 1) {
              key = keys[0];
              value = it[key];
            } else {
              throw new TypeError(`Expected tuple with one key, not ${keys.length} keys`);
            }
          } else {
            key = it;
          }
          pairs2.items.push(Pair.createPair(key, value, ctx));
        }
      return pairs2;
    }
    var pairs = {
      collection: "seq",
      default: false,
      tag: "tag:yaml.org,2002:pairs",
      resolve: resolvePairs,
      createNode: createPairs
    };
    exports.createPairs = createPairs;
    exports.pairs = pairs;
    exports.resolvePairs = resolvePairs;
  }
});

// node_modules/yaml/dist/schema/yaml-1.1/omap.js
var require_omap = __commonJS({
  "node_modules/yaml/dist/schema/yaml-1.1/omap.js"(exports) {
    "use strict";
    var identity = require_identity();
    var toJS = require_toJS();
    var YAMLMap = require_YAMLMap();
    var YAMLSeq = require_YAMLSeq();
    var pairs = require_pairs();
    var YAMLOMap = class _YAMLOMap extends YAMLSeq.YAMLSeq {
      constructor() {
        super();
        this.add = YAMLMap.YAMLMap.prototype.add.bind(this);
        this.delete = YAMLMap.YAMLMap.prototype.delete.bind(this);
        this.get = YAMLMap.YAMLMap.prototype.get.bind(this);
        this.has = YAMLMap.YAMLMap.prototype.has.bind(this);
        this.set = YAMLMap.YAMLMap.prototype.set.bind(this);
        this.tag = _YAMLOMap.tag;
      }
      /**
       * If `ctx` is given, the return type is actually `Map<unknown, unknown>`,
       * but TypeScript won't allow widening the signature of a child method.
       */
      toJSON(_, ctx) {
        if (!ctx)
          return super.toJSON(_);
        const map = /* @__PURE__ */ new Map();
        if (ctx?.onCreate)
          ctx.onCreate(map);
        for (const pair of this.items) {
          let key, value;
          if (identity.isPair(pair)) {
            key = toJS.toJS(pair.key, "", ctx);
            value = toJS.toJS(pair.value, key, ctx);
          } else {
            key = toJS.toJS(pair, "", ctx);
          }
          if (map.has(key))
            throw new Error("Ordered maps must not include duplicate keys");
          map.set(key, value);
        }
        return map;
      }
      static from(schema, iterable, ctx) {
        const pairs$1 = pairs.createPairs(schema, iterable, ctx);
        const omap2 = new this();
        omap2.items = pairs$1.items;
        return omap2;
      }
    };
    YAMLOMap.tag = "tag:yaml.org,2002:omap";
    var omap = {
      collection: "seq",
      identify: (value) => value instanceof Map,
      nodeClass: YAMLOMap,
      default: false,
      tag: "tag:yaml.org,2002:omap",
      resolve(seq, onError) {
        const pairs$1 = pairs.resolvePairs(seq, onError);
        const seenKeys = [];
        for (const { key } of pairs$1.items) {
          if (identity.isScalar(key)) {
            if (seenKeys.includes(key.value)) {
              onError(`Ordered maps must not include duplicate keys: ${key.value}`);
            } else {
              seenKeys.push(key.value);
            }
          }
        }
        return Object.assign(new YAMLOMap(), pairs$1);
      },
      createNode: (schema, iterable, ctx) => YAMLOMap.from(schema, iterable, ctx)
    };
    exports.YAMLOMap = YAMLOMap;
    exports.omap = omap;
  }
});

// node_modules/yaml/dist/schema/yaml-1.1/bool.js
var require_bool2 = __commonJS({
  "node_modules/yaml/dist/schema/yaml-1.1/bool.js"(exports) {
    "use strict";
    var Scalar = require_Scalar();
    function boolStringify({ value, source }, ctx) {
      const boolObj = value ? trueTag : falseTag;
      if (source && boolObj.test.test(source))
        return source;
      return value ? ctx.options.trueStr : ctx.options.falseStr;
    }
    var trueTag = {
      identify: (value) => value === true,
      default: true,
      tag: "tag:yaml.org,2002:bool",
      test: /^(?:Y|y|[Yy]es|YES|[Tt]rue|TRUE|[Oo]n|ON)$/,
      resolve: () => new Scalar.Scalar(true),
      stringify: boolStringify
    };
    var falseTag = {
      identify: (value) => value === false,
      default: true,
      tag: "tag:yaml.org,2002:bool",
      test: /^(?:N|n|[Nn]o|NO|[Ff]alse|FALSE|[Oo]ff|OFF)$/,
      resolve: () => new Scalar.Scalar(false),
      stringify: boolStringify
    };
    exports.falseTag = falseTag;
    exports.trueTag = trueTag;
  }
});

// node_modules/yaml/dist/schema/yaml-1.1/float.js
var require_float2 = __commonJS({
  "node_modules/yaml/dist/schema/yaml-1.1/float.js"(exports) {
    "use strict";
    var Scalar = require_Scalar();
    var stringifyNumber = require_stringifyNumber();
    var floatNaN = {
      identify: (value) => typeof value === "number",
      default: true,
      tag: "tag:yaml.org,2002:float",
      test: /^(?:[-+]?\.(?:inf|Inf|INF)|\.nan|\.NaN|\.NAN)$/,
      resolve: (str) => str.slice(-3).toLowerCase() === "nan" ? NaN : str[0] === "-" ? Number.NEGATIVE_INFINITY : Number.POSITIVE_INFINITY,
      stringify: stringifyNumber.stringifyNumber
    };
    var floatExp = {
      identify: (value) => typeof value === "number",
      default: true,
      tag: "tag:yaml.org,2002:float",
      format: "EXP",
      test: /^[-+]?(?:[0-9][0-9_]*)?(?:\.[0-9_]*)?[eE][-+]?[0-9]+$/,
      resolve: (str) => parseFloat(str.replace(/_/g, "")),
      stringify(node) {
        const num = Number(node.value);
        return isFinite(num) ? num.toExponential() : stringifyNumber.stringifyNumber(node);
      }
    };
    var float = {
      identify: (value) => typeof value === "number",
      default: true,
      tag: "tag:yaml.org,2002:float",
      test: /^[-+]?(?:[0-9][0-9_]*)?\.[0-9_]*$/,
      resolve(str) {
        const node = new Scalar.Scalar(parseFloat(str.replace(/_/g, "")));
        const dot = str.indexOf(".");
        if (dot !== -1) {
          const f = str.substring(dot + 1).replace(/_/g, "");
          if (f[f.length - 1] === "0")
            node.minFractionDigits = f.length;
        }
        return node;
      },
      stringify: stringifyNumber.stringifyNumber
    };
    exports.float = float;
    exports.floatExp = floatExp;
    exports.floatNaN = floatNaN;
  }
});

// node_modules/yaml/dist/schema/yaml-1.1/int.js
var require_int2 = __commonJS({
  "node_modules/yaml/dist/schema/yaml-1.1/int.js"(exports) {
    "use strict";
    var stringifyNumber = require_stringifyNumber();
    var intIdentify = (value) => typeof value === "bigint" || Number.isInteger(value);
    function intResolve(str, offset, radix, { intAsBigInt }) {
      const sign = str[0];
      if (sign === "-" || sign === "+")
        offset += 1;
      str = str.substring(offset).replace(/_/g, "");
      if (intAsBigInt) {
        switch (radix) {
          case 2:
            str = `0b${str}`;
            break;
          case 8:
            str = `0o${str}`;
            break;
          case 16:
            str = `0x${str}`;
            break;
        }
        const n2 = BigInt(str);
        return sign === "-" ? BigInt(-1) * n2 : n2;
      }
      const n = parseInt(str, radix);
      return sign === "-" ? -1 * n : n;
    }
    function intStringify(node, radix, prefix) {
      const { value } = node;
      if (intIdentify(value)) {
        const str = value.toString(radix);
        return value < 0 ? "-" + prefix + str.substr(1) : prefix + str;
      }
      return stringifyNumber.stringifyNumber(node);
    }
    var intBin = {
      identify: intIdentify,
      default: true,
      tag: "tag:yaml.org,2002:int",
      format: "BIN",
      test: /^[-+]?0b[0-1_]+$/,
      resolve: (str, _onError, opt) => intResolve(str, 2, 2, opt),
      stringify: (node) => intStringify(node, 2, "0b")
    };
    var intOct = {
      identify: intIdentify,
      default: true,
      tag: "tag:yaml.org,2002:int",
      format: "OCT",
      test: /^[-+]?0[0-7_]+$/,
      resolve: (str, _onError, opt) => intResolve(str, 1, 8, opt),
      stringify: (node) => intStringify(node, 8, "0")
    };
    var int = {
      identify: intIdentify,
      default: true,
      tag: "tag:yaml.org,2002:int",
      test: /^[-+]?[0-9][0-9_]*$/,
      resolve: (str, _onError, opt) => intResolve(str, 0, 10, opt),
      stringify: stringifyNumber.stringifyNumber
    };
    var intHex = {
      identify: intIdentify,
      default: true,
      tag: "tag:yaml.org,2002:int",
      format: "HEX",
      test: /^[-+]?0x[0-9a-fA-F_]+$/,
      resolve: (str, _onError, opt) => intResolve(str, 2, 16, opt),
      stringify: (node) => intStringify(node, 16, "0x")
    };
    exports.int = int;
    exports.intBin = intBin;
    exports.intHex = intHex;
    exports.intOct = intOct;
  }
});

// node_modules/yaml/dist/schema/yaml-1.1/set.js
var require_set = __commonJS({
  "node_modules/yaml/dist/schema/yaml-1.1/set.js"(exports) {
    "use strict";
    var identity = require_identity();
    var Pair = require_Pair();
    var YAMLMap = require_YAMLMap();
    var YAMLSet = class _YAMLSet extends YAMLMap.YAMLMap {
      constructor(schema) {
        super(schema);
        this.tag = _YAMLSet.tag;
      }
      add(key) {
        let pair;
        if (identity.isPair(key))
          pair = key;
        else if (key && typeof key === "object" && "key" in key && "value" in key && key.value === null)
          pair = new Pair.Pair(key.key, null);
        else
          pair = new Pair.Pair(key, null);
        const prev = YAMLMap.findPair(this.items, pair.key);
        if (!prev)
          this.items.push(pair);
      }
      /**
       * If `keepPair` is `true`, returns the Pair matching `key`.
       * Otherwise, returns the value of that Pair's key.
       */
      get(key, keepPair) {
        const pair = YAMLMap.findPair(this.items, key);
        return !keepPair && identity.isPair(pair) ? identity.isScalar(pair.key) ? pair.key.value : pair.key : pair;
      }
      set(key, value) {
        if (typeof value !== "boolean")
          throw new Error(`Expected boolean value for set(key, value) in a YAML set, not ${typeof value}`);
        const prev = YAMLMap.findPair(this.items, key);
        if (prev && !value) {
          this.items.splice(this.items.indexOf(prev), 1);
        } else if (!prev && value) {
          this.items.push(new Pair.Pair(key));
        }
      }
      toJSON(_, ctx) {
        return super.toJSON(_, ctx, Set);
      }
      toString(ctx, onComment, onChompKeep) {
        if (!ctx)
          return JSON.stringify(this);
        if (this.hasAllNullValues(true))
          return super.toString(Object.assign({}, ctx, { allNullValues: true }), onComment, onChompKeep);
        else
          throw new Error("Set items must all have null values");
      }
      static from(schema, iterable, ctx) {
        const { replacer } = ctx;
        const set2 = new this(schema);
        if (iterable && Symbol.iterator in Object(iterable))
          for (let value of iterable) {
            if (typeof replacer === "function")
              value = replacer.call(iterable, value, value);
            set2.items.push(Pair.createPair(value, null, ctx));
          }
        return set2;
      }
    };
    YAMLSet.tag = "tag:yaml.org,2002:set";
    var set = {
      collection: "map",
      identify: (value) => value instanceof Set,
      nodeClass: YAMLSet,
      default: false,
      tag: "tag:yaml.org,2002:set",
      createNode: (schema, iterable, ctx) => YAMLSet.from(schema, iterable, ctx),
      resolve(map, onError) {
        if (identity.isMap(map)) {
          if (map.hasAllNullValues(true))
            return Object.assign(new YAMLSet(), map);
          else
            onError("Set items must all have null values");
        } else
          onError("Expected a mapping for this tag");
        return map;
      }
    };
    exports.YAMLSet = YAMLSet;
    exports.set = set;
  }
});

// node_modules/yaml/dist/schema/yaml-1.1/timestamp.js
var require_timestamp = __commonJS({
  "node_modules/yaml/dist/schema/yaml-1.1/timestamp.js"(exports) {
    "use strict";
    var stringifyNumber = require_stringifyNumber();
    function parseSexagesimal(str, asBigInt) {
      const sign = str[0];
      const parts = sign === "-" || sign === "+" ? str.substring(1) : str;
      const num = (n) => asBigInt ? BigInt(n) : Number(n);
      const res = parts.replace(/_/g, "").split(":").reduce((res2, p) => res2 * num(60) + num(p), num(0));
      return sign === "-" ? num(-1) * res : res;
    }
    function stringifySexagesimal(node) {
      let { value } = node;
      let num = (n) => n;
      if (typeof value === "bigint")
        num = (n) => BigInt(n);
      else if (isNaN(value) || !isFinite(value))
        return stringifyNumber.stringifyNumber(node);
      let sign = "";
      if (value < 0) {
        sign = "-";
        value *= num(-1);
      }
      const _60 = num(60);
      const parts = [value % _60];
      if (value < 60) {
        parts.unshift(0);
      } else {
        value = (value - parts[0]) / _60;
        parts.unshift(value % _60);
        if (value >= 60) {
          value = (value - parts[0]) / _60;
          parts.unshift(value);
        }
      }
      return sign + parts.map((n) => String(n).padStart(2, "0")).join(":").replace(/000000\d*$/, "");
    }
    var intTime = {
      identify: (value) => typeof value === "bigint" || Number.isInteger(value),
      default: true,
      tag: "tag:yaml.org,2002:int",
      format: "TIME",
      test: /^[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+$/,
      resolve: (str, _onError, { intAsBigInt }) => parseSexagesimal(str, intAsBigInt),
      stringify: stringifySexagesimal
    };
    var floatTime = {
      identify: (value) => typeof value === "number",
      default: true,
      tag: "tag:yaml.org,2002:float",
      format: "TIME",
      test: /^[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*$/,
      resolve: (str) => parseSexagesimal(str, false),
      stringify: stringifySexagesimal
    };
    var timestamp = {
      identify: (value) => value instanceof Date,
      default: true,
      tag: "tag:yaml.org,2002:timestamp",
      // If the time zone is omitted, the timestamp is assumed to be specified in UTC. The time part
      // may be omitted altogether, resulting in a date format. In such a case, the time part is
      // assumed to be 00:00:00Z (start of day, UTC).
      test: RegExp("^([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})(?:(?:t|T|[ \\t]+)([0-9]{1,2}):([0-9]{1,2}):([0-9]{1,2}(\\.[0-9]+)?)(?:[ \\t]*(Z|[-+][012]?[0-9](?::[0-9]{2})?))?)?$"),
      resolve(str) {
        const match = str.match(timestamp.test);
        if (!match)
          throw new Error("!!timestamp expects a date, starting with yyyy-mm-dd");
        const [, year, month, day, hour, minute, second] = match.map(Number);
        const millisec = match[7] ? Number((match[7] + "00").substr(1, 3)) : 0;
        let date = Date.UTC(year, month - 1, day, hour || 0, minute || 0, second || 0, millisec);
        const tz = match[8];
        if (tz && tz !== "Z") {
          let d = parseSexagesimal(tz, false);
          if (Math.abs(d) < 30)
            d *= 60;
          date -= 6e4 * d;
        }
        return new Date(date);
      },
      stringify: ({ value }) => value?.toISOString().replace(/(T00:00:00)?\.000Z$/, "") ?? ""
    };
    exports.floatTime = floatTime;
    exports.intTime = intTime;
    exports.timestamp = timestamp;
  }
});

// node_modules/yaml/dist/schema/yaml-1.1/schema.js
var require_schema3 = __commonJS({
  "node_modules/yaml/dist/schema/yaml-1.1/schema.js"(exports) {
    "use strict";
    var map = require_map();
    var _null = require_null();
    var seq = require_seq();
    var string = require_string();
    var binary = require_binary();
    var bool2 = require_bool2();
    var float = require_float2();
    var int = require_int2();
    var merge = require_merge();
    var omap = require_omap();
    var pairs = require_pairs();
    var set = require_set();
    var timestamp = require_timestamp();
    var schema = [
      map.map,
      seq.seq,
      string.string,
      _null.nullTag,
      bool2.trueTag,
      bool2.falseTag,
      int.intBin,
      int.intOct,
      int.int,
      int.intHex,
      float.floatNaN,
      float.floatExp,
      float.float,
      binary.binary,
      merge.merge,
      omap.omap,
      pairs.pairs,
      set.set,
      timestamp.intTime,
      timestamp.floatTime,
      timestamp.timestamp
    ];
    exports.schema = schema;
  }
});

// node_modules/yaml/dist/schema/tags.js
var require_tags = __commonJS({
  "node_modules/yaml/dist/schema/tags.js"(exports) {
    "use strict";
    var map = require_map();
    var _null = require_null();
    var seq = require_seq();
    var string = require_string();
    var bool2 = require_bool();
    var float = require_float();
    var int = require_int();
    var schema = require_schema();
    var schema$1 = require_schema2();
    var binary = require_binary();
    var merge = require_merge();
    var omap = require_omap();
    var pairs = require_pairs();
    var schema$2 = require_schema3();
    var set = require_set();
    var timestamp = require_timestamp();
    var schemas = /* @__PURE__ */ new Map([
      ["core", schema.schema],
      ["failsafe", [map.map, seq.seq, string.string]],
      ["json", schema$1.schema],
      ["yaml11", schema$2.schema],
      ["yaml-1.1", schema$2.schema]
    ]);
    var tagsByName = {
      binary: binary.binary,
      bool: bool2.boolTag,
      float: float.float,
      floatExp: float.floatExp,
      floatNaN: float.floatNaN,
      floatTime: timestamp.floatTime,
      int: int.int,
      intHex: int.intHex,
      intOct: int.intOct,
      intTime: timestamp.intTime,
      map: map.map,
      merge: merge.merge,
      null: _null.nullTag,
      omap: omap.omap,
      pairs: pairs.pairs,
      seq: seq.seq,
      set: set.set,
      timestamp: timestamp.timestamp
    };
    var coreKnownTags = {
      "tag:yaml.org,2002:binary": binary.binary,
      "tag:yaml.org,2002:merge": merge.merge,
      "tag:yaml.org,2002:omap": omap.omap,
      "tag:yaml.org,2002:pairs": pairs.pairs,
      "tag:yaml.org,2002:set": set.set,
      "tag:yaml.org,2002:timestamp": timestamp.timestamp
    };
    function getTags(customTags, schemaName, addMergeTag) {
      const schemaTags = schemas.get(schemaName);
      if (schemaTags && !customTags) {
        return addMergeTag && !schemaTags.includes(merge.merge) ? schemaTags.concat(merge.merge) : schemaTags.slice();
      }
      let tags = schemaTags;
      if (!tags) {
        if (Array.isArray(customTags))
          tags = [];
        else {
          const keys = Array.from(schemas.keys()).filter((key) => key !== "yaml11").map((key) => JSON.stringify(key)).join(", ");
          throw new Error(`Unknown schema "${schemaName}"; use one of ${keys} or define customTags array`);
        }
      }
      if (Array.isArray(customTags)) {
        for (const tag of customTags)
          tags = tags.concat(tag);
      } else if (typeof customTags === "function") {
        tags = customTags(tags.slice());
      }
      if (addMergeTag)
        tags = tags.concat(merge.merge);
      return tags.reduce((tags2, tag) => {
        const tagObj = typeof tag === "string" ? tagsByName[tag] : tag;
        if (!tagObj) {
          const tagName = JSON.stringify(tag);
          const keys = Object.keys(tagsByName).map((key) => JSON.stringify(key)).join(", ");
          throw new Error(`Unknown custom tag ${tagName}; use one of ${keys}`);
        }
        if (!tags2.includes(tagObj))
          tags2.push(tagObj);
        return tags2;
      }, []);
    }
    exports.coreKnownTags = coreKnownTags;
    exports.getTags = getTags;
  }
});

// node_modules/yaml/dist/schema/Schema.js
var require_Schema = __commonJS({
  "node_modules/yaml/dist/schema/Schema.js"(exports) {
    "use strict";
    var identity = require_identity();
    var map = require_map();
    var seq = require_seq();
    var string = require_string();
    var tags = require_tags();
    var sortMapEntriesByKey = (a, b) => a.key < b.key ? -1 : a.key > b.key ? 1 : 0;
    var Schema = class _Schema {
      constructor({ compat, customTags, merge, resolveKnownTags, schema, sortMapEntries, toStringDefaults }) {
        this.compat = Array.isArray(compat) ? tags.getTags(compat, "compat") : compat ? tags.getTags(null, compat) : null;
        this.name = typeof schema === "string" && schema || "core";
        this.knownTags = resolveKnownTags ? tags.coreKnownTags : {};
        this.tags = tags.getTags(customTags, this.name, merge);
        this.toStringOptions = toStringDefaults ?? null;
        Object.defineProperty(this, identity.MAP, { value: map.map });
        Object.defineProperty(this, identity.SCALAR, { value: string.string });
        Object.defineProperty(this, identity.SEQ, { value: seq.seq });
        this.sortMapEntries = typeof sortMapEntries === "function" ? sortMapEntries : sortMapEntries === true ? sortMapEntriesByKey : null;
      }
      clone() {
        const copy = Object.create(_Schema.prototype, Object.getOwnPropertyDescriptors(this));
        copy.tags = this.tags.slice();
        return copy;
      }
    };
    exports.Schema = Schema;
  }
});

// node_modules/yaml/dist/stringify/stringifyDocument.js
var require_stringifyDocument = __commonJS({
  "node_modules/yaml/dist/stringify/stringifyDocument.js"(exports) {
    "use strict";
    var identity = require_identity();
    var stringify = require_stringify();
    var stringifyComment = require_stringifyComment();
    function stringifyDocument(doc, options) {
      const lines = [];
      let hasDirectives = options.directives === true;
      if (options.directives !== false && doc.directives) {
        const dir = doc.directives.toString(doc);
        if (dir) {
          lines.push(dir);
          hasDirectives = true;
        } else if (doc.directives.docStart)
          hasDirectives = true;
      }
      if (hasDirectives)
        lines.push("---");
      const ctx = stringify.createStringifyContext(doc, options);
      const { commentString } = ctx.options;
      if (doc.commentBefore) {
        if (lines.length !== 1)
          lines.unshift("");
        const cs = commentString(doc.commentBefore);
        lines.unshift(stringifyComment.indentComment(cs, ""));
      }
      let chompKeep = false;
      let contentComment = null;
      if (doc.contents) {
        if (identity.isNode(doc.contents)) {
          if (doc.contents.spaceBefore && hasDirectives)
            lines.push("");
          if (doc.contents.commentBefore) {
            const cs = commentString(doc.contents.commentBefore);
            lines.push(stringifyComment.indentComment(cs, ""));
          }
          ctx.forceBlockIndent = !!doc.comment;
          contentComment = doc.contents.comment;
        }
        const onChompKeep = contentComment ? void 0 : () => chompKeep = true;
        let body = stringify.stringify(doc.contents, ctx, () => contentComment = null, onChompKeep);
        if (contentComment)
          body += stringifyComment.lineComment(body, "", commentString(contentComment));
        if ((body[0] === "|" || body[0] === ">") && lines[lines.length - 1] === "---") {
          lines[lines.length - 1] = `--- ${body}`;
        } else
          lines.push(body);
      } else {
        lines.push(stringify.stringify(doc.contents, ctx));
      }
      if (doc.directives?.docEnd) {
        if (doc.comment) {
          const cs = commentString(doc.comment);
          if (cs.includes("\n")) {
            lines.push("...");
            lines.push(stringifyComment.indentComment(cs, ""));
          } else {
            lines.push(`... ${cs}`);
          }
        } else {
          lines.push("...");
        }
      } else {
        let dc = doc.comment;
        if (dc && chompKeep)
          dc = dc.replace(/^\n+/, "");
        if (dc) {
          if ((!chompKeep || contentComment) && lines[lines.length - 1] !== "")
            lines.push("");
          lines.push(stringifyComment.indentComment(commentString(dc), ""));
        }
      }
      return lines.join("\n") + "\n";
    }
    exports.stringifyDocument = stringifyDocument;
  }
});

// node_modules/yaml/dist/doc/Document.js
var require_Document = __commonJS({
  "node_modules/yaml/dist/doc/Document.js"(exports) {
    "use strict";
    var Alias = require_Alias();
    var Collection = require_Collection();
    var identity = require_identity();
    var Pair = require_Pair();
    var toJS = require_toJS();
    var Schema = require_Schema();
    var stringifyDocument = require_stringifyDocument();
    var anchors = require_anchors();
    var applyReviver = require_applyReviver();
    var createNode = require_createNode();
    var directives = require_directives();
    var Document = class _Document {
      constructor(value, replacer, options) {
        this.commentBefore = null;
        this.comment = null;
        this.errors = [];
        this.warnings = [];
        Object.defineProperty(this, identity.NODE_TYPE, { value: identity.DOC });
        let _replacer = null;
        if (typeof replacer === "function" || Array.isArray(replacer)) {
          _replacer = replacer;
        } else if (options === void 0 && replacer) {
          options = replacer;
          replacer = void 0;
        }
        const opt = Object.assign({
          intAsBigInt: false,
          keepSourceTokens: false,
          logLevel: "warn",
          prettyErrors: true,
          strict: true,
          stringKeys: false,
          uniqueKeys: true,
          version: "1.2"
        }, options);
        this.options = opt;
        let { version } = opt;
        if (options?._directives) {
          this.directives = options._directives.atDocument();
          if (this.directives.yaml.explicit)
            version = this.directives.yaml.version;
        } else
          this.directives = new directives.Directives({ version });
        this.setSchema(version, options);
        this.contents = value === void 0 ? null : this.createNode(value, _replacer, options);
      }
      /**
       * Create a deep copy of this Document and its contents.
       *
       * Custom Node values that inherit from `Object` still refer to their original instances.
       */
      clone() {
        const copy = Object.create(_Document.prototype, {
          [identity.NODE_TYPE]: { value: identity.DOC }
        });
        copy.commentBefore = this.commentBefore;
        copy.comment = this.comment;
        copy.errors = this.errors.slice();
        copy.warnings = this.warnings.slice();
        copy.options = Object.assign({}, this.options);
        if (this.directives)
          copy.directives = this.directives.clone();
        copy.schema = this.schema.clone();
        copy.contents = identity.isNode(this.contents) ? this.contents.clone(copy.schema) : this.contents;
        if (this.range)
          copy.range = this.range.slice();
        return copy;
      }
      /** Adds a value to the document. */
      add(value) {
        if (assertCollection(this.contents))
          this.contents.add(value);
      }
      /** Adds a value to the document. */
      addIn(path, value) {
        if (assertCollection(this.contents))
          this.contents.addIn(path, value);
      }
      /**
       * Create a new `Alias` node, ensuring that the target `node` has the required anchor.
       *
       * If `node` already has an anchor, `name` is ignored.
       * Otherwise, the `node.anchor` value will be set to `name`,
       * or if an anchor with that name is already present in the document,
       * `name` will be used as a prefix for a new unique anchor.
       * If `name` is undefined, the generated anchor will use 'a' as a prefix.
       */
      createAlias(node, name) {
        if (!node.anchor) {
          const prev = anchors.anchorNames(this);
          node.anchor = // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing
          !name || prev.has(name) ? anchors.findNewAnchor(name || "a", prev) : name;
        }
        return new Alias.Alias(node.anchor);
      }
      createNode(value, replacer, options) {
        let _replacer = void 0;
        if (typeof replacer === "function") {
          value = replacer.call({ "": value }, "", value);
          _replacer = replacer;
        } else if (Array.isArray(replacer)) {
          const keyToStr = (v) => typeof v === "number" || v instanceof String || v instanceof Number;
          const asStr = replacer.filter(keyToStr).map(String);
          if (asStr.length > 0)
            replacer = replacer.concat(asStr);
          _replacer = replacer;
        } else if (options === void 0 && replacer) {
          options = replacer;
          replacer = void 0;
        }
        const { aliasDuplicateObjects, anchorPrefix, flow, keepUndefined, onTagObj, tag } = options ?? {};
        const { onAnchor, setAnchors, sourceObjects } = anchors.createNodeAnchors(
          this,
          // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing
          anchorPrefix || "a"
        );
        const ctx = {
          aliasDuplicateObjects: aliasDuplicateObjects ?? true,
          keepUndefined: keepUndefined ?? false,
          onAnchor,
          onTagObj,
          replacer: _replacer,
          schema: this.schema,
          sourceObjects
        };
        const node = createNode.createNode(value, tag, ctx);
        if (flow && identity.isCollection(node))
          node.flow = true;
        setAnchors();
        return node;
      }
      /**
       * Convert a key and a value into a `Pair` using the current schema,
       * recursively wrapping all values as `Scalar` or `Collection` nodes.
       */
      createPair(key, value, options = {}) {
        const k = this.createNode(key, null, options);
        const v = this.createNode(value, null, options);
        return new Pair.Pair(k, v);
      }
      /**
       * Removes a value from the document.
       * @returns `true` if the item was found and removed.
       */
      delete(key) {
        return assertCollection(this.contents) ? this.contents.delete(key) : false;
      }
      /**
       * Removes a value from the document.
       * @returns `true` if the item was found and removed.
       */
      deleteIn(path) {
        if (Collection.isEmptyPath(path)) {
          if (this.contents == null)
            return false;
          this.contents = null;
          return true;
        }
        return assertCollection(this.contents) ? this.contents.deleteIn(path) : false;
      }
      /**
       * Returns item at `key`, or `undefined` if not found. By default unwraps
       * scalar values from their surrounding node; to disable set `keepScalar` to
       * `true` (collections are always returned intact).
       */
      get(key, keepScalar) {
        return identity.isCollection(this.contents) ? this.contents.get(key, keepScalar) : void 0;
      }
      /**
       * Returns item at `path`, or `undefined` if not found. By default unwraps
       * scalar values from their surrounding node; to disable set `keepScalar` to
       * `true` (collections are always returned intact).
       */
      getIn(path, keepScalar) {
        if (Collection.isEmptyPath(path))
          return !keepScalar && identity.isScalar(this.contents) ? this.contents.value : this.contents;
        return identity.isCollection(this.contents) ? this.contents.getIn(path, keepScalar) : void 0;
      }
      /**
       * Checks if the document includes a value with the key `key`.
       */
      has(key) {
        return identity.isCollection(this.contents) ? this.contents.has(key) : false;
      }
      /**
       * Checks if the document includes a value at `path`.
       */
      hasIn(path) {
        if (Collection.isEmptyPath(path))
          return this.contents !== void 0;
        return identity.isCollection(this.contents) ? this.contents.hasIn(path) : false;
      }
      /**
       * Sets a value in this document. For `!!set`, `value` needs to be a
       * boolean to add/remove the item from the set.
       */
      set(key, value) {
        if (this.contents == null) {
          this.contents = Collection.collectionFromPath(this.schema, [key], value);
        } else if (assertCollection(this.contents)) {
          this.contents.set(key, value);
        }
      }
      /**
       * Sets a value in this document. For `!!set`, `value` needs to be a
       * boolean to add/remove the item from the set.
       */
      setIn(path, value) {
        if (Collection.isEmptyPath(path)) {
          this.contents = value;
        } else if (this.contents == null) {
          this.contents = Collection.collectionFromPath(this.schema, Array.from(path), value);
        } else if (assertCollection(this.contents)) {
          this.contents.setIn(path, value);
        }
      }
      /**
       * Change the YAML version and schema used by the document.
       * A `null` version disables support for directives, explicit tags, anchors, and aliases.
       * It also requires the `schema` option to be given as a `Schema` instance value.
       *
       * Overrides all previously set schema options.
       */
      setSchema(version, options = {}) {
        if (typeof version === "number")
          version = String(version);
        let opt;
        switch (version) {
          case "1.1":
            if (this.directives)
              this.directives.yaml.version = "1.1";
            else
              this.directives = new directives.Directives({ version: "1.1" });
            opt = { resolveKnownTags: false, schema: "yaml-1.1" };
            break;
          case "1.2":
          case "next":
            if (this.directives)
              this.directives.yaml.version = version;
            else
              this.directives = new directives.Directives({ version });
            opt = { resolveKnownTags: true, schema: "core" };
            break;
          case null:
            if (this.directives)
              delete this.directives;
            opt = null;
            break;
          default: {
            const sv = JSON.stringify(version);
            throw new Error(`Expected '1.1', '1.2' or null as first argument, but found: ${sv}`);
          }
        }
        if (options.schema instanceof Object)
          this.schema = options.schema;
        else if (opt)
          this.schema = new Schema.Schema(Object.assign(opt, options));
        else
          throw new Error(`With a null YAML version, the { schema: Schema } option is required`);
      }
      // json & jsonArg are only used from toJSON()
      toJS({ json, jsonArg, mapAsMap, maxAliasCount, onAnchor, reviver } = {}) {
        const ctx = {
          anchors: /* @__PURE__ */ new Map(),
          doc: this,
          keep: !json,
          mapAsMap: mapAsMap === true,
          mapKeyWarned: false,
          maxAliasCount: typeof maxAliasCount === "number" ? maxAliasCount : 100
        };
        const res = toJS.toJS(this.contents, jsonArg ?? "", ctx);
        if (typeof onAnchor === "function")
          for (const { count, res: res2 } of ctx.anchors.values())
            onAnchor(res2, count);
        return typeof reviver === "function" ? applyReviver.applyReviver(reviver, { "": res }, "", res) : res;
      }
      /**
       * A JSON representation of the document `contents`.
       *
       * @param jsonArg Used by `JSON.stringify` to indicate the array index or
       *   property name.
       */
      toJSON(jsonArg, onAnchor) {
        return this.toJS({ json: true, jsonArg, mapAsMap: false, onAnchor });
      }
      /** A YAML representation of the document. */
      toString(options = {}) {
        if (this.errors.length > 0)
          throw new Error("Document with errors cannot be stringified");
        if ("indent" in options && (!Number.isInteger(options.indent) || Number(options.indent) <= 0)) {
          const s = JSON.stringify(options.indent);
          throw new Error(`"indent" option must be a positive integer, not ${s}`);
        }
        return stringifyDocument.stringifyDocument(this, options);
      }
    };
    function assertCollection(contents) {
      if (identity.isCollection(contents))
        return true;
      throw new Error("Expected a YAML collection as document contents");
    }
    exports.Document = Document;
  }
});

// node_modules/yaml/dist/errors.js
var require_errors = __commonJS({
  "node_modules/yaml/dist/errors.js"(exports) {
    "use strict";
    var YAMLError = class extends Error {
      constructor(name, pos, code, message) {
        super();
        this.name = name;
        this.code = code;
        this.message = message;
        this.pos = pos;
      }
    };
    var YAMLParseError = class extends YAMLError {
      constructor(pos, code, message) {
        super("YAMLParseError", pos, code, message);
      }
    };
    var YAMLWarning = class extends YAMLError {
      constructor(pos, code, message) {
        super("YAMLWarning", pos, code, message);
      }
    };
    var prettifyError = (src, lc) => (error) => {
      if (error.pos[0] === -1)
        return;
      error.linePos = error.pos.map((pos) => lc.linePos(pos));
      const { line, col } = error.linePos[0];
      error.message += ` at line ${line}, column ${col}`;
      let ci = col - 1;
      let lineStr = src.substring(lc.lineStarts[line - 1], lc.lineStarts[line]).replace(/[\n\r]+$/, "");
      if (ci >= 60 && lineStr.length > 80) {
        const trimStart = Math.min(ci - 39, lineStr.length - 79);
        lineStr = "…" + lineStr.substring(trimStart);
        ci -= trimStart - 1;
      }
      if (lineStr.length > 80)
        lineStr = lineStr.substring(0, 79) + "…";
      if (line > 1 && /^ *$/.test(lineStr.substring(0, ci))) {
        let prev = src.substring(lc.lineStarts[line - 2], lc.lineStarts[line - 1]);
        if (prev.length > 80)
          prev = prev.substring(0, 79) + "…\n";
        lineStr = prev + lineStr;
      }
      if (/[^ ]/.test(lineStr)) {
        let count = 1;
        const end = error.linePos[1];
        if (end?.line === line && end.col > col) {
          count = Math.max(1, Math.min(end.col - col, 80 - ci));
        }
        const pointer = " ".repeat(ci) + "^".repeat(count);
        error.message += `:

${lineStr}
${pointer}
`;
      }
    };
    exports.YAMLError = YAMLError;
    exports.YAMLParseError = YAMLParseError;
    exports.YAMLWarning = YAMLWarning;
    exports.prettifyError = prettifyError;
  }
});

// node_modules/yaml/dist/compose/resolve-props.js
var require_resolve_props = __commonJS({
  "node_modules/yaml/dist/compose/resolve-props.js"(exports) {
    "use strict";
    function resolveProps(tokens, { flow, indicator, next, offset, onError, parentIndent, startOnNewline }) {
      let spaceBefore = false;
      let atNewline = startOnNewline;
      let hasSpace = startOnNewline;
      let comment = "";
      let commentSep = "";
      let hasNewline = false;
      let reqSpace = false;
      let tab = null;
      let anchor = null;
      let tag = null;
      let newlineAfterProp = null;
      let comma = null;
      let found = null;
      let start = null;
      for (const token of tokens) {
        if (reqSpace) {
          if (token.type !== "space" && token.type !== "newline" && token.type !== "comma")
            onError(token.offset, "MISSING_CHAR", "Tags and anchors must be separated from the next token by white space");
          reqSpace = false;
        }
        if (tab) {
          if (atNewline && token.type !== "comment" && token.type !== "newline") {
            onError(tab, "TAB_AS_INDENT", "Tabs are not allowed as indentation");
          }
          tab = null;
        }
        switch (token.type) {
          case "space":
            if (!flow && (indicator !== "doc-start" || next?.type !== "flow-collection") && token.source.includes("	")) {
              tab = token;
            }
            hasSpace = true;
            break;
          case "comment": {
            if (!hasSpace)
              onError(token, "MISSING_CHAR", "Comments must be separated from other tokens by white space characters");
            const cb = token.source.substring(1) || " ";
            if (!comment)
              comment = cb;
            else
              comment += commentSep + cb;
            commentSep = "";
            atNewline = false;
            break;
          }
          case "newline":
            if (atNewline) {
              if (comment)
                comment += token.source;
              else if (!found || indicator !== "seq-item-ind")
                spaceBefore = true;
            } else
              commentSep += token.source;
            atNewline = true;
            hasNewline = true;
            if (anchor || tag)
              newlineAfterProp = token;
            hasSpace = true;
            break;
          case "anchor":
            if (anchor)
              onError(token, "MULTIPLE_ANCHORS", "A node can have at most one anchor");
            if (token.source.endsWith(":"))
              onError(token.offset + token.source.length - 1, "BAD_ALIAS", "Anchor ending in : is ambiguous", true);
            anchor = token;
            start ?? (start = token.offset);
            atNewline = false;
            hasSpace = false;
            reqSpace = true;
            break;
          case "tag": {
            if (tag)
              onError(token, "MULTIPLE_TAGS", "A node can have at most one tag");
            tag = token;
            start ?? (start = token.offset);
            atNewline = false;
            hasSpace = false;
            reqSpace = true;
            break;
          }
          case indicator:
            if (anchor || tag)
              onError(token, "BAD_PROP_ORDER", `Anchors and tags must be after the ${token.source} indicator`);
            if (found)
              onError(token, "UNEXPECTED_TOKEN", `Unexpected ${token.source} in ${flow ?? "collection"}`);
            found = token;
            atNewline = indicator === "seq-item-ind" || indicator === "explicit-key-ind";
            hasSpace = false;
            break;
          case "comma":
            if (flow) {
              if (comma)
                onError(token, "UNEXPECTED_TOKEN", `Unexpected , in ${flow}`);
              comma = token;
              atNewline = false;
              hasSpace = false;
              break;
            }
          // else fallthrough
          default:
            onError(token, "UNEXPECTED_TOKEN", `Unexpected ${token.type} token`);
            atNewline = false;
            hasSpace = false;
        }
      }
      const last = tokens[tokens.length - 1];
      const end = last ? last.offset + last.source.length : offset;
      if (reqSpace && next && next.type !== "space" && next.type !== "newline" && next.type !== "comma" && (next.type !== "scalar" || next.source !== "")) {
        onError(next.offset, "MISSING_CHAR", "Tags and anchors must be separated from the next token by white space");
      }
      if (tab && (atNewline && tab.indent <= parentIndent || next?.type === "block-map" || next?.type === "block-seq"))
        onError(tab, "TAB_AS_INDENT", "Tabs are not allowed as indentation");
      return {
        comma,
        found,
        spaceBefore,
        comment,
        hasNewline,
        anchor,
        tag,
        newlineAfterProp,
        end,
        start: start ?? end
      };
    }
    exports.resolveProps = resolveProps;
  }
});

// node_modules/yaml/dist/compose/util-contains-newline.js
var require_util_contains_newline = __commonJS({
  "node_modules/yaml/dist/compose/util-contains-newline.js"(exports) {
    "use strict";
    function containsNewline(key) {
      if (!key)
        return null;
      switch (key.type) {
        case "alias":
        case "scalar":
        case "double-quoted-scalar":
        case "single-quoted-scalar":
          if (key.source.includes("\n"))
            return true;
          if (key.end) {
            for (const st of key.end)
              if (st.type === "newline")
                return true;
          }
          return false;
        case "flow-collection":
          for (const it of key.items) {
            for (const st of it.start)
              if (st.type === "newline")
                return true;
            if (it.sep) {
              for (const st of it.sep)
                if (st.type === "newline")
                  return true;
            }
            if (containsNewline(it.key) || containsNewline(it.value))
              return true;
          }
          return false;
        default:
          return true;
      }
    }
    exports.containsNewline = containsNewline;
  }
});

// node_modules/yaml/dist/compose/util-flow-indent-check.js
var require_util_flow_indent_check = __commonJS({
  "node_modules/yaml/dist/compose/util-flow-indent-check.js"(exports) {
    "use strict";
    var utilContainsNewline = require_util_contains_newline();
    function flowIndentCheck(indent, fc, onError) {
      if (fc?.type === "flow-collection") {
        const end = fc.end[0];
        if (end.indent === indent && (end.source === "]" || end.source === "}") && utilContainsNewline.containsNewline(fc)) {
          const msg = "Flow end indicator should be more indented than parent";
          onError(end, "BAD_INDENT", msg, true);
        }
      }
    }
    exports.flowIndentCheck = flowIndentCheck;
  }
});

// node_modules/yaml/dist/compose/util-map-includes.js
var require_util_map_includes = __commonJS({
  "node_modules/yaml/dist/compose/util-map-includes.js"(exports) {
    "use strict";
    var identity = require_identity();
    function mapIncludes(ctx, items, search) {
      const { uniqueKeys } = ctx.options;
      if (uniqueKeys === false)
        return false;
      const isEqual = typeof uniqueKeys === "function" ? uniqueKeys : (a, b) => a === b || identity.isScalar(a) && identity.isScalar(b) && a.value === b.value;
      return items.some((pair) => isEqual(pair.key, search));
    }
    exports.mapIncludes = mapIncludes;
  }
});

// node_modules/yaml/dist/compose/resolve-block-map.js
var require_resolve_block_map = __commonJS({
  "node_modules/yaml/dist/compose/resolve-block-map.js"(exports) {
    "use strict";
    var Pair = require_Pair();
    var YAMLMap = require_YAMLMap();
    var resolveProps = require_resolve_props();
    var utilContainsNewline = require_util_contains_newline();
    var utilFlowIndentCheck = require_util_flow_indent_check();
    var utilMapIncludes = require_util_map_includes();
    var startColMsg = "All mapping items must start at the same column";
    function resolveBlockMap({ composeNode, composeEmptyNode }, ctx, bm, onError, tag) {
      const NodeClass = tag?.nodeClass ?? YAMLMap.YAMLMap;
      const map = new NodeClass(ctx.schema);
      if (ctx.atRoot)
        ctx.atRoot = false;
      let offset = bm.offset;
      let commentEnd = null;
      for (const collItem of bm.items) {
        const { start, key, sep: sep2, value } = collItem;
        const keyProps = resolveProps.resolveProps(start, {
          indicator: "explicit-key-ind",
          next: key ?? sep2?.[0],
          offset,
          onError,
          parentIndent: bm.indent,
          startOnNewline: true
        });
        const implicitKey = !keyProps.found;
        if (implicitKey) {
          if (key) {
            if (key.type === "block-seq")
              onError(offset, "BLOCK_AS_IMPLICIT_KEY", "A block sequence may not be used as an implicit map key");
            else if ("indent" in key && key.indent !== bm.indent)
              onError(offset, "BAD_INDENT", startColMsg);
          }
          if (!keyProps.anchor && !keyProps.tag && !sep2) {
            commentEnd = keyProps.end;
            if (keyProps.comment) {
              if (map.comment)
                map.comment += "\n" + keyProps.comment;
              else
                map.comment = keyProps.comment;
            }
            continue;
          }
          if (keyProps.newlineAfterProp || utilContainsNewline.containsNewline(key)) {
            onError(key ?? start[start.length - 1], "MULTILINE_IMPLICIT_KEY", "Implicit keys need to be on a single line");
          }
        } else if (keyProps.found?.indent !== bm.indent) {
          onError(offset, "BAD_INDENT", startColMsg);
        }
        ctx.atKey = true;
        const keyStart = keyProps.end;
        const keyNode = key ? composeNode(ctx, key, keyProps, onError) : composeEmptyNode(ctx, keyStart, start, null, keyProps, onError);
        if (ctx.schema.compat)
          utilFlowIndentCheck.flowIndentCheck(bm.indent, key, onError);
        ctx.atKey = false;
        if (utilMapIncludes.mapIncludes(ctx, map.items, keyNode))
          onError(keyStart, "DUPLICATE_KEY", "Map keys must be unique");
        const valueProps = resolveProps.resolveProps(sep2 ?? [], {
          indicator: "map-value-ind",
          next: value,
          offset: keyNode.range[2],
          onError,
          parentIndent: bm.indent,
          startOnNewline: !key || key.type === "block-scalar"
        });
        offset = valueProps.end;
        if (valueProps.found) {
          if (implicitKey) {
            if (value?.type === "block-map" && !valueProps.hasNewline)
              onError(offset, "BLOCK_AS_IMPLICIT_KEY", "Nested mappings are not allowed in compact mappings");
            if (ctx.options.strict && keyProps.start < valueProps.found.offset - 1024)
              onError(keyNode.range, "KEY_OVER_1024_CHARS", "The : indicator must be at most 1024 chars after the start of an implicit block mapping key");
          }
          const valueNode = value ? composeNode(ctx, value, valueProps, onError) : composeEmptyNode(ctx, offset, sep2, null, valueProps, onError);
          if (ctx.schema.compat)
            utilFlowIndentCheck.flowIndentCheck(bm.indent, value, onError);
          offset = valueNode.range[2];
          const pair = new Pair.Pair(keyNode, valueNode);
          if (ctx.options.keepSourceTokens)
            pair.srcToken = collItem;
          map.items.push(pair);
        } else {
          if (implicitKey)
            onError(keyNode.range, "MISSING_CHAR", "Implicit map keys need to be followed by map values");
          if (valueProps.comment) {
            if (keyNode.comment)
              keyNode.comment += "\n" + valueProps.comment;
            else
              keyNode.comment = valueProps.comment;
          }
          const pair = new Pair.Pair(keyNode);
          if (ctx.options.keepSourceTokens)
            pair.srcToken = collItem;
          map.items.push(pair);
        }
      }
      if (commentEnd && commentEnd < offset)
        onError(commentEnd, "IMPOSSIBLE", "Map comment with trailing content");
      map.range = [bm.offset, offset, commentEnd ?? offset];
      return map;
    }
    exports.resolveBlockMap = resolveBlockMap;
  }
});

// node_modules/yaml/dist/compose/resolve-block-seq.js
var require_resolve_block_seq = __commonJS({
  "node_modules/yaml/dist/compose/resolve-block-seq.js"(exports) {
    "use strict";
    var YAMLSeq = require_YAMLSeq();
    var resolveProps = require_resolve_props();
    var utilFlowIndentCheck = require_util_flow_indent_check();
    function resolveBlockSeq({ composeNode, composeEmptyNode }, ctx, bs, onError, tag) {
      const NodeClass = tag?.nodeClass ?? YAMLSeq.YAMLSeq;
      const seq = new NodeClass(ctx.schema);
      if (ctx.atRoot)
        ctx.atRoot = false;
      if (ctx.atKey)
        ctx.atKey = false;
      let offset = bs.offset;
      let commentEnd = null;
      for (const { start, value } of bs.items) {
        const props = resolveProps.resolveProps(start, {
          indicator: "seq-item-ind",
          next: value,
          offset,
          onError,
          parentIndent: bs.indent,
          startOnNewline: true
        });
        if (!props.found) {
          if (props.anchor || props.tag || value) {
            if (value?.type === "block-seq")
              onError(props.end, "BAD_INDENT", "All sequence items must start at the same column");
            else
              onError(offset, "MISSING_CHAR", "Sequence item without - indicator");
          } else {
            commentEnd = props.end;
            if (props.comment)
              seq.comment = props.comment;
            continue;
          }
        }
        const node = value ? composeNode(ctx, value, props, onError) : composeEmptyNode(ctx, props.end, start, null, props, onError);
        if (ctx.schema.compat)
          utilFlowIndentCheck.flowIndentCheck(bs.indent, value, onError);
        offset = node.range[2];
        seq.items.push(node);
      }
      seq.range = [bs.offset, offset, commentEnd ?? offset];
      return seq;
    }
    exports.resolveBlockSeq = resolveBlockSeq;
  }
});

// node_modules/yaml/dist/compose/resolve-end.js
var require_resolve_end = __commonJS({
  "node_modules/yaml/dist/compose/resolve-end.js"(exports) {
    "use strict";
    function resolveEnd(end, offset, reqSpace, onError) {
      let comment = "";
      if (end) {
        let hasSpace = false;
        let sep2 = "";
        for (const token of end) {
          const { source, type } = token;
          switch (type) {
            case "space":
              hasSpace = true;
              break;
            case "comment": {
              if (reqSpace && !hasSpace)
                onError(token, "MISSING_CHAR", "Comments must be separated from other tokens by white space characters");
              const cb = source.substring(1) || " ";
              if (!comment)
                comment = cb;
              else
                comment += sep2 + cb;
              sep2 = "";
              break;
            }
            case "newline":
              if (comment)
                sep2 += source;
              hasSpace = true;
              break;
            default:
              onError(token, "UNEXPECTED_TOKEN", `Unexpected ${type} at node end`);
          }
          offset += source.length;
        }
      }
      return { comment, offset };
    }
    exports.resolveEnd = resolveEnd;
  }
});

// node_modules/yaml/dist/compose/resolve-flow-collection.js
var require_resolve_flow_collection = __commonJS({
  "node_modules/yaml/dist/compose/resolve-flow-collection.js"(exports) {
    "use strict";
    var identity = require_identity();
    var Pair = require_Pair();
    var YAMLMap = require_YAMLMap();
    var YAMLSeq = require_YAMLSeq();
    var resolveEnd = require_resolve_end();
    var resolveProps = require_resolve_props();
    var utilContainsNewline = require_util_contains_newline();
    var utilMapIncludes = require_util_map_includes();
    var blockMsg = "Block collections are not allowed within flow collections";
    var isBlock = (token) => token && (token.type === "block-map" || token.type === "block-seq");
    function resolveFlowCollection({ composeNode, composeEmptyNode }, ctx, fc, onError, tag) {
      const isMap = fc.start.source === "{";
      const fcName = isMap ? "flow map" : "flow sequence";
      const NodeClass = tag?.nodeClass ?? (isMap ? YAMLMap.YAMLMap : YAMLSeq.YAMLSeq);
      const coll = new NodeClass(ctx.schema);
      coll.flow = true;
      const atRoot = ctx.atRoot;
      if (atRoot)
        ctx.atRoot = false;
      if (ctx.atKey)
        ctx.atKey = false;
      let offset = fc.offset + fc.start.source.length;
      for (let i = 0; i < fc.items.length; ++i) {
        const collItem = fc.items[i];
        const { start, key, sep: sep2, value } = collItem;
        const props = resolveProps.resolveProps(start, {
          flow: fcName,
          indicator: "explicit-key-ind",
          next: key ?? sep2?.[0],
          offset,
          onError,
          parentIndent: fc.indent,
          startOnNewline: false
        });
        if (!props.found) {
          if (!props.anchor && !props.tag && !sep2 && !value) {
            if (i === 0 && props.comma)
              onError(props.comma, "UNEXPECTED_TOKEN", `Unexpected , in ${fcName}`);
            else if (i < fc.items.length - 1)
              onError(props.start, "UNEXPECTED_TOKEN", `Unexpected empty item in ${fcName}`);
            if (props.comment) {
              if (coll.comment)
                coll.comment += "\n" + props.comment;
              else
                coll.comment = props.comment;
            }
            offset = props.end;
            continue;
          }
          if (!isMap && ctx.options.strict && utilContainsNewline.containsNewline(key))
            onError(
              key,
              // checked by containsNewline()
              "MULTILINE_IMPLICIT_KEY",
              "Implicit keys of flow sequence pairs need to be on a single line"
            );
        }
        if (i === 0) {
          if (props.comma)
            onError(props.comma, "UNEXPECTED_TOKEN", `Unexpected , in ${fcName}`);
        } else {
          if (!props.comma)
            onError(props.start, "MISSING_CHAR", `Missing , between ${fcName} items`);
          if (props.comment) {
            let prevItemComment = "";
            loop: for (const st of start) {
              switch (st.type) {
                case "comma":
                case "space":
                  break;
                case "comment":
                  prevItemComment = st.source.substring(1);
                  break loop;
                default:
                  break loop;
              }
            }
            if (prevItemComment) {
              let prev = coll.items[coll.items.length - 1];
              if (identity.isPair(prev))
                prev = prev.value ?? prev.key;
              if (prev.comment)
                prev.comment += "\n" + prevItemComment;
              else
                prev.comment = prevItemComment;
              props.comment = props.comment.substring(prevItemComment.length + 1);
            }
          }
        }
        if (!isMap && !sep2 && !props.found) {
          const valueNode = value ? composeNode(ctx, value, props, onError) : composeEmptyNode(ctx, props.end, sep2, null, props, onError);
          coll.items.push(valueNode);
          offset = valueNode.range[2];
          if (isBlock(value))
            onError(valueNode.range, "BLOCK_IN_FLOW", blockMsg);
        } else {
          ctx.atKey = true;
          const keyStart = props.end;
          const keyNode = key ? composeNode(ctx, key, props, onError) : composeEmptyNode(ctx, keyStart, start, null, props, onError);
          if (isBlock(key))
            onError(keyNode.range, "BLOCK_IN_FLOW", blockMsg);
          ctx.atKey = false;
          const valueProps = resolveProps.resolveProps(sep2 ?? [], {
            flow: fcName,
            indicator: "map-value-ind",
            next: value,
            offset: keyNode.range[2],
            onError,
            parentIndent: fc.indent,
            startOnNewline: false
          });
          if (valueProps.found) {
            if (!isMap && !props.found && ctx.options.strict) {
              if (sep2)
                for (const st of sep2) {
                  if (st === valueProps.found)
                    break;
                  if (st.type === "newline") {
                    onError(st, "MULTILINE_IMPLICIT_KEY", "Implicit keys of flow sequence pairs need to be on a single line");
                    break;
                  }
                }
              if (props.start < valueProps.found.offset - 1024)
                onError(valueProps.found, "KEY_OVER_1024_CHARS", "The : indicator must be at most 1024 chars after the start of an implicit flow sequence key");
            }
          } else if (value) {
            if ("source" in value && value.source?.[0] === ":")
              onError(value, "MISSING_CHAR", `Missing space after : in ${fcName}`);
            else
              onError(valueProps.start, "MISSING_CHAR", `Missing , or : between ${fcName} items`);
          }
          const valueNode = value ? composeNode(ctx, value, valueProps, onError) : valueProps.found ? composeEmptyNode(ctx, valueProps.end, sep2, null, valueProps, onError) : null;
          if (valueNode) {
            if (isBlock(value))
              onError(valueNode.range, "BLOCK_IN_FLOW", blockMsg);
          } else if (valueProps.comment) {
            if (keyNode.comment)
              keyNode.comment += "\n" + valueProps.comment;
            else
              keyNode.comment = valueProps.comment;
          }
          const pair = new Pair.Pair(keyNode, valueNode);
          if (ctx.options.keepSourceTokens)
            pair.srcToken = collItem;
          if (isMap) {
            const map = coll;
            if (utilMapIncludes.mapIncludes(ctx, map.items, keyNode))
              onError(keyStart, "DUPLICATE_KEY", "Map keys must be unique");
            map.items.push(pair);
          } else {
            const map = new YAMLMap.YAMLMap(ctx.schema);
            map.flow = true;
            map.items.push(pair);
            const endRange = (valueNode ?? keyNode).range;
            map.range = [keyNode.range[0], endRange[1], endRange[2]];
            coll.items.push(map);
          }
          offset = valueNode ? valueNode.range[2] : valueProps.end;
        }
      }
      const expectedEnd = isMap ? "}" : "]";
      const [ce, ...ee] = fc.end;
      let cePos = offset;
      if (ce?.source === expectedEnd)
        cePos = ce.offset + ce.source.length;
      else {
        const name = fcName[0].toUpperCase() + fcName.substring(1);
        const msg = atRoot ? `${name} must end with a ${expectedEnd}` : `${name} in block collection must be sufficiently indented and end with a ${expectedEnd}`;
        onError(offset, atRoot ? "MISSING_CHAR" : "BAD_INDENT", msg);
        if (ce && ce.source.length !== 1)
          ee.unshift(ce);
      }
      if (ee.length > 0) {
        const end = resolveEnd.resolveEnd(ee, cePos, ctx.options.strict, onError);
        if (end.comment) {
          if (coll.comment)
            coll.comment += "\n" + end.comment;
          else
            coll.comment = end.comment;
        }
        coll.range = [fc.offset, cePos, end.offset];
      } else {
        coll.range = [fc.offset, cePos, cePos];
      }
      return coll;
    }
    exports.resolveFlowCollection = resolveFlowCollection;
  }
});

// node_modules/yaml/dist/compose/compose-collection.js
var require_compose_collection = __commonJS({
  "node_modules/yaml/dist/compose/compose-collection.js"(exports) {
    "use strict";
    var identity = require_identity();
    var Scalar = require_Scalar();
    var YAMLMap = require_YAMLMap();
    var YAMLSeq = require_YAMLSeq();
    var resolveBlockMap = require_resolve_block_map();
    var resolveBlockSeq = require_resolve_block_seq();
    var resolveFlowCollection = require_resolve_flow_collection();
    function resolveCollection(CN, ctx, token, onError, tagName, tag) {
      const coll = token.type === "block-map" ? resolveBlockMap.resolveBlockMap(CN, ctx, token, onError, tag) : token.type === "block-seq" ? resolveBlockSeq.resolveBlockSeq(CN, ctx, token, onError, tag) : resolveFlowCollection.resolveFlowCollection(CN, ctx, token, onError, tag);
      const Coll = coll.constructor;
      if (tagName === "!" || tagName === Coll.tagName) {
        coll.tag = Coll.tagName;
        return coll;
      }
      if (tagName)
        coll.tag = tagName;
      return coll;
    }
    function composeCollection(CN, ctx, token, props, onError) {
      const tagToken = props.tag;
      const tagName = !tagToken ? null : ctx.directives.tagName(tagToken.source, (msg) => onError(tagToken, "TAG_RESOLVE_FAILED", msg));
      if (token.type === "block-seq") {
        const { anchor, newlineAfterProp: nl } = props;
        const lastProp = anchor && tagToken ? anchor.offset > tagToken.offset ? anchor : tagToken : anchor ?? tagToken;
        if (lastProp && (!nl || nl.offset < lastProp.offset)) {
          const message = "Missing newline after block sequence props";
          onError(lastProp, "MISSING_CHAR", message);
        }
      }
      const expType = token.type === "block-map" ? "map" : token.type === "block-seq" ? "seq" : token.start.source === "{" ? "map" : "seq";
      if (!tagToken || !tagName || tagName === "!" || tagName === YAMLMap.YAMLMap.tagName && expType === "map" || tagName === YAMLSeq.YAMLSeq.tagName && expType === "seq") {
        return resolveCollection(CN, ctx, token, onError, tagName);
      }
      let tag = ctx.schema.tags.find((t) => t.tag === tagName && t.collection === expType);
      if (!tag) {
        const kt = ctx.schema.knownTags[tagName];
        if (kt?.collection === expType) {
          ctx.schema.tags.push(Object.assign({}, kt, { default: false }));
          tag = kt;
        } else {
          if (kt) {
            onError(tagToken, "BAD_COLLECTION_TYPE", `${kt.tag} used for ${expType} collection, but expects ${kt.collection ?? "scalar"}`, true);
          } else {
            onError(tagToken, "TAG_RESOLVE_FAILED", `Unresolved tag: ${tagName}`, true);
          }
          return resolveCollection(CN, ctx, token, onError, tagName);
        }
      }
      const coll = resolveCollection(CN, ctx, token, onError, tagName, tag);
      const res = tag.resolve?.(coll, (msg) => onError(tagToken, "TAG_RESOLVE_FAILED", msg), ctx.options) ?? coll;
      const node = identity.isNode(res) ? res : new Scalar.Scalar(res);
      node.range = coll.range;
      node.tag = tagName;
      if (tag?.format)
        node.format = tag.format;
      return node;
    }
    exports.composeCollection = composeCollection;
  }
});

// node_modules/yaml/dist/compose/resolve-block-scalar.js
var require_resolve_block_scalar = __commonJS({
  "node_modules/yaml/dist/compose/resolve-block-scalar.js"(exports) {
    "use strict";
    var Scalar = require_Scalar();
    function resolveBlockScalar(ctx, scalar, onError) {
      const start = scalar.offset;
      const header = parseBlockScalarHeader(scalar, ctx.options.strict, onError);
      if (!header)
        return { value: "", type: null, comment: "", range: [start, start, start] };
      const type = header.mode === ">" ? Scalar.Scalar.BLOCK_FOLDED : Scalar.Scalar.BLOCK_LITERAL;
      const lines = scalar.source ? splitLines(scalar.source) : [];
      let chompStart = lines.length;
      for (let i = lines.length - 1; i >= 0; --i) {
        const content = lines[i][1];
        if (content === "" || content === "\r")
          chompStart = i;
        else
          break;
      }
      if (chompStart === 0) {
        const value2 = header.chomp === "+" && lines.length > 0 ? "\n".repeat(Math.max(1, lines.length - 1)) : "";
        let end2 = start + header.length;
        if (scalar.source)
          end2 += scalar.source.length;
        return { value: value2, type, comment: header.comment, range: [start, end2, end2] };
      }
      let trimIndent = scalar.indent + header.indent;
      let offset = scalar.offset + header.length;
      let contentStart = 0;
      for (let i = 0; i < chompStart; ++i) {
        const [indent, content] = lines[i];
        if (content === "" || content === "\r") {
          if (header.indent === 0 && indent.length > trimIndent)
            trimIndent = indent.length;
        } else {
          if (indent.length < trimIndent) {
            const message = "Block scalars with more-indented leading empty lines must use an explicit indentation indicator";
            onError(offset + indent.length, "MISSING_CHAR", message);
          }
          if (header.indent === 0)
            trimIndent = indent.length;
          contentStart = i;
          if (trimIndent === 0 && !ctx.atRoot) {
            const message = "Block scalar values in collections must be indented";
            onError(offset, "BAD_INDENT", message);
          }
          break;
        }
        offset += indent.length + content.length + 1;
      }
      for (let i = lines.length - 1; i >= chompStart; --i) {
        if (lines[i][0].length > trimIndent)
          chompStart = i + 1;
      }
      let value = "";
      let sep2 = "";
      let prevMoreIndented = false;
      for (let i = 0; i < contentStart; ++i)
        value += lines[i][0].slice(trimIndent) + "\n";
      for (let i = contentStart; i < chompStart; ++i) {
        let [indent, content] = lines[i];
        offset += indent.length + content.length + 1;
        const crlf = content[content.length - 1] === "\r";
        if (crlf)
          content = content.slice(0, -1);
        if (content && indent.length < trimIndent) {
          const src = header.indent ? "explicit indentation indicator" : "first line";
          const message = `Block scalar lines must not be less indented than their ${src}`;
          onError(offset - content.length - (crlf ? 2 : 1), "BAD_INDENT", message);
          indent = "";
        }
        if (type === Scalar.Scalar.BLOCK_LITERAL) {
          value += sep2 + indent.slice(trimIndent) + content;
          sep2 = "\n";
        } else if (indent.length > trimIndent || content[0] === "	") {
          if (sep2 === " ")
            sep2 = "\n";
          else if (!prevMoreIndented && sep2 === "\n")
            sep2 = "\n\n";
          value += sep2 + indent.slice(trimIndent) + content;
          sep2 = "\n";
          prevMoreIndented = true;
        } else if (content === "") {
          if (sep2 === "\n")
            value += "\n";
          else
            sep2 = "\n";
        } else {
          value += sep2 + content;
          sep2 = " ";
          prevMoreIndented = false;
        }
      }
      switch (header.chomp) {
        case "-":
          break;
        case "+":
          for (let i = chompStart; i < lines.length; ++i)
            value += "\n" + lines[i][0].slice(trimIndent);
          if (value[value.length - 1] !== "\n")
            value += "\n";
          break;
        default:
          value += "\n";
      }
      const end = start + header.length + scalar.source.length;
      return { value, type, comment: header.comment, range: [start, end, end] };
    }
    function parseBlockScalarHeader({ offset, props }, strict, onError) {
      if (props[0].type !== "block-scalar-header") {
        onError(props[0], "IMPOSSIBLE", "Block scalar header not found");
        return null;
      }
      const { source } = props[0];
      const mode = source[0];
      let indent = 0;
      let chomp = "";
      let error = -1;
      for (let i = 1; i < source.length; ++i) {
        const ch = source[i];
        if (!chomp && (ch === "-" || ch === "+"))
          chomp = ch;
        else {
          const n = Number(ch);
          if (!indent && n)
            indent = n;
          else if (error === -1)
            error = offset + i;
        }
      }
      if (error !== -1)
        onError(error, "UNEXPECTED_TOKEN", `Block scalar header includes extra characters: ${source}`);
      let hasSpace = false;
      let comment = "";
      let length = source.length;
      for (let i = 1; i < props.length; ++i) {
        const token = props[i];
        switch (token.type) {
          case "space":
            hasSpace = true;
          // fallthrough
          case "newline":
            length += token.source.length;
            break;
          case "comment":
            if (strict && !hasSpace) {
              const message = "Comments must be separated from other tokens by white space characters";
              onError(token, "MISSING_CHAR", message);
            }
            length += token.source.length;
            comment = token.source.substring(1);
            break;
          case "error":
            onError(token, "UNEXPECTED_TOKEN", token.message);
            length += token.source.length;
            break;
          /* istanbul ignore next should not happen */
          default: {
            const message = `Unexpected token in block scalar header: ${token.type}`;
            onError(token, "UNEXPECTED_TOKEN", message);
            const ts = token.source;
            if (ts && typeof ts === "string")
              length += ts.length;
          }
        }
      }
      return { mode, indent, chomp, comment, length };
    }
    function splitLines(source) {
      const split = source.split(/\n( *)/);
      const first = split[0];
      const m = first.match(/^( *)/);
      const line0 = m?.[1] ? [m[1], first.slice(m[1].length)] : ["", first];
      const lines = [line0];
      for (let i = 1; i < split.length; i += 2)
        lines.push([split[i], split[i + 1]]);
      return lines;
    }
    exports.resolveBlockScalar = resolveBlockScalar;
  }
});

// node_modules/yaml/dist/compose/resolve-flow-scalar.js
var require_resolve_flow_scalar = __commonJS({
  "node_modules/yaml/dist/compose/resolve-flow-scalar.js"(exports) {
    "use strict";
    var Scalar = require_Scalar();
    var resolveEnd = require_resolve_end();
    function resolveFlowScalar(scalar, strict, onError) {
      const { offset, type, source, end } = scalar;
      let _type;
      let value;
      const _onError = (rel, code, msg) => onError(offset + rel, code, msg);
      switch (type) {
        case "scalar":
          _type = Scalar.Scalar.PLAIN;
          value = plainValue(source, _onError);
          break;
        case "single-quoted-scalar":
          _type = Scalar.Scalar.QUOTE_SINGLE;
          value = singleQuotedValue(source, _onError);
          break;
        case "double-quoted-scalar":
          _type = Scalar.Scalar.QUOTE_DOUBLE;
          value = doubleQuotedValue(source, _onError);
          break;
        /* istanbul ignore next should not happen */
        default:
          onError(scalar, "UNEXPECTED_TOKEN", `Expected a flow scalar value, but found: ${type}`);
          return {
            value: "",
            type: null,
            comment: "",
            range: [offset, offset + source.length, offset + source.length]
          };
      }
      const valueEnd = offset + source.length;
      const re = resolveEnd.resolveEnd(end, valueEnd, strict, onError);
      return {
        value,
        type: _type,
        comment: re.comment,
        range: [offset, valueEnd, re.offset]
      };
    }
    function plainValue(source, onError) {
      let badChar = "";
      switch (source[0]) {
        /* istanbul ignore next should not happen */
        case "	":
          badChar = "a tab character";
          break;
        case ",":
          badChar = "flow indicator character ,";
          break;
        case "%":
          badChar = "directive indicator character %";
          break;
        case "|":
        case ">": {
          badChar = `block scalar indicator ${source[0]}`;
          break;
        }
        case "@":
        case "`": {
          badChar = `reserved character ${source[0]}`;
          break;
        }
      }
      if (badChar)
        onError(0, "BAD_SCALAR_START", `Plain value cannot start with ${badChar}`);
      return unfoldLines(source);
    }
    function singleQuotedValue(source, onError) {
      if (source[source.length - 1] !== "'" || source.length === 1)
        onError(source.length, "MISSING_CHAR", "Missing closing 'quote");
      return unfoldLines(source.slice(1, -1)).replace(/''/g, "'");
    }
    function unfoldLines(source) {
      const line = /(.*?)\r?\n/sy;
      let match = line.exec(source);
      if (!match)
        return source;
      let trimEnd, trimBoth;
      try {
        trimEnd = new RegExp("(?<![ 	])[ 	]+$");
        trimBoth = new RegExp("^[ 	]+|(?<![ 	])[ 	]+$", "g");
      } catch {
        trimEnd = /[ \t]+$/;
        trimBoth = /^[ \t]+|[ \t]+$/g;
      }
      let res = match[1].replace(trimEnd, "");
      let sep2 = " ";
      let pos = line.lastIndex;
      while (match = line.exec(source)) {
        const lm = match[1].replace(trimBoth, "");
        if (lm === "") {
          if (sep2 === "\n")
            res += sep2;
          else
            sep2 = "\n";
        } else {
          res += sep2 + lm;
          sep2 = " ";
        }
        pos = line.lastIndex;
      }
      const last = /[ \t]*(.*)/sy;
      last.lastIndex = pos;
      match = last.exec(source);
      return res + sep2 + (match?.[1] ?? "");
    }
    function doubleQuotedValue(source, onError) {
      let res = "";
      for (let i = 1; i < source.length - 1; ++i) {
        const ch = source[i];
        if (ch === "\r" && source[i + 1] === "\n")
          continue;
        if (ch === "\n") {
          const { fold, offset } = foldNewline(source, i);
          res += fold;
          i = offset;
        } else if (ch === "\\") {
          let next = source[++i];
          const cc = escapeCodes[next];
          if (cc)
            res += cc;
          else if (next === "\n") {
            next = source[i + 1];
            while (next === " " || next === "	")
              next = source[++i + 1];
          } else if (next === "\r" && source[i + 1] === "\n") {
            next = source[++i + 1];
            while (next === " " || next === "	")
              next = source[++i + 1];
          } else if (next === "x" || next === "u" || next === "U") {
            const length = next === "x" ? 2 : next === "u" ? 4 : 8;
            res += parseCharCode(source, i + 1, length, onError);
            i += length;
          } else {
            const raw = source.substr(i - 1, 2);
            onError(i - 1, "BAD_DQ_ESCAPE", `Invalid escape sequence ${raw}`);
            res += raw;
          }
        } else if (ch === " " || ch === "	") {
          const wsStart = i;
          let next = source[i + 1];
          while (next === " " || next === "	")
            next = source[++i + 1];
          if (next !== "\n" && !(next === "\r" && source[i + 2] === "\n"))
            res += i > wsStart ? source.slice(wsStart, i + 1) : ch;
        } else {
          res += ch;
        }
      }
      if (source[source.length - 1] !== '"' || source.length === 1)
        onError(source.length, "MISSING_CHAR", 'Missing closing "quote');
      return res;
    }
    function foldNewline(source, offset) {
      let fold = "";
      let ch = source[offset + 1];
      while (ch === " " || ch === "	" || ch === "\n" || ch === "\r") {
        if (ch === "\r" && source[offset + 2] !== "\n")
          break;
        if (ch === "\n")
          fold += "\n";
        offset += 1;
        ch = source[offset + 1];
      }
      if (!fold)
        fold = " ";
      return { fold, offset };
    }
    var escapeCodes = {
      "0": "\0",
      // null character
      a: "\x07",
      // bell character
      b: "\b",
      // backspace
      e: "\x1B",
      // escape character
      f: "\f",
      // form feed
      n: "\n",
      // line feed
      r: "\r",
      // carriage return
      t: "	",
      // horizontal tab
      v: "\v",
      // vertical tab
      N: "",
      // Unicode next line
      _: " ",
      // Unicode non-breaking space
      L: "\u2028",
      // Unicode line separator
      P: "\u2029",
      // Unicode paragraph separator
      " ": " ",
      '"': '"',
      "/": "/",
      "\\": "\\",
      "	": "	"
    };
    function parseCharCode(source, offset, length, onError) {
      const cc = source.substr(offset, length);
      const ok = cc.length === length && /^[0-9a-fA-F]+$/.test(cc);
      const code = ok ? parseInt(cc, 16) : NaN;
      try {
        return String.fromCodePoint(code);
      } catch {
        const raw = source.substr(offset - 2, length + 2);
        onError(offset - 2, "BAD_DQ_ESCAPE", `Invalid escape sequence ${raw}`);
        return raw;
      }
    }
    exports.resolveFlowScalar = resolveFlowScalar;
  }
});

// node_modules/yaml/dist/compose/compose-scalar.js
var require_compose_scalar = __commonJS({
  "node_modules/yaml/dist/compose/compose-scalar.js"(exports) {
    "use strict";
    var identity = require_identity();
    var Scalar = require_Scalar();
    var resolveBlockScalar = require_resolve_block_scalar();
    var resolveFlowScalar = require_resolve_flow_scalar();
    function composeScalar(ctx, token, tagToken, onError) {
      const { value, type, comment, range } = token.type === "block-scalar" ? resolveBlockScalar.resolveBlockScalar(ctx, token, onError) : resolveFlowScalar.resolveFlowScalar(token, ctx.options.strict, onError);
      const tagName = tagToken ? ctx.directives.tagName(tagToken.source, (msg) => onError(tagToken, "TAG_RESOLVE_FAILED", msg)) : null;
      let tag;
      if (ctx.options.stringKeys && ctx.atKey) {
        tag = ctx.schema[identity.SCALAR];
      } else if (tagName)
        tag = findScalarTagByName(ctx.schema, value, tagName, tagToken, onError);
      else if (token.type === "scalar")
        tag = findScalarTagByTest(ctx, value, token, onError);
      else
        tag = ctx.schema[identity.SCALAR];
      let scalar;
      try {
        const res = tag.resolve(value, (msg) => onError(tagToken ?? token, "TAG_RESOLVE_FAILED", msg), ctx.options);
        scalar = identity.isScalar(res) ? res : new Scalar.Scalar(res);
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        onError(tagToken ?? token, "TAG_RESOLVE_FAILED", msg);
        scalar = new Scalar.Scalar(value);
      }
      scalar.range = range;
      scalar.source = value;
      if (type)
        scalar.type = type;
      if (tagName)
        scalar.tag = tagName;
      if (tag.format)
        scalar.format = tag.format;
      if (comment)
        scalar.comment = comment;
      return scalar;
    }
    function findScalarTagByName(schema, value, tagName, tagToken, onError) {
      if (tagName === "!")
        return schema[identity.SCALAR];
      const matchWithTest = [];
      for (const tag of schema.tags) {
        if (!tag.collection && tag.tag === tagName) {
          if (tag.default && tag.test)
            matchWithTest.push(tag);
          else
            return tag;
        }
      }
      for (const tag of matchWithTest)
        if (tag.test?.test(value))
          return tag;
      const kt = schema.knownTags[tagName];
      if (kt && !kt.collection) {
        schema.tags.push(Object.assign({}, kt, { default: false, test: void 0 }));
        return kt;
      }
      onError(tagToken, "TAG_RESOLVE_FAILED", `Unresolved tag: ${tagName}`, tagName !== "tag:yaml.org,2002:str");
      return schema[identity.SCALAR];
    }
    function findScalarTagByTest({ atKey, directives, schema }, value, token, onError) {
      const tag = schema.tags.find((tag2) => (tag2.default === true || atKey && tag2.default === "key") && tag2.test?.test(value)) || schema[identity.SCALAR];
      if (schema.compat) {
        const compat = schema.compat.find((tag2) => tag2.default && tag2.test?.test(value)) ?? schema[identity.SCALAR];
        if (tag.tag !== compat.tag) {
          const ts = directives.tagString(tag.tag);
          const cs = directives.tagString(compat.tag);
          const msg = `Value may be parsed as either ${ts} or ${cs}`;
          onError(token, "TAG_RESOLVE_FAILED", msg, true);
        }
      }
      return tag;
    }
    exports.composeScalar = composeScalar;
  }
});

// node_modules/yaml/dist/compose/util-empty-scalar-position.js
var require_util_empty_scalar_position = __commonJS({
  "node_modules/yaml/dist/compose/util-empty-scalar-position.js"(exports) {
    "use strict";
    function emptyScalarPosition(offset, before, pos) {
      if (before) {
        pos ?? (pos = before.length);
        for (let i = pos - 1; i >= 0; --i) {
          let st = before[i];
          switch (st.type) {
            case "space":
            case "comment":
            case "newline":
              offset -= st.source.length;
              continue;
          }
          st = before[++i];
          while (st?.type === "space") {
            offset += st.source.length;
            st = before[++i];
          }
          break;
        }
      }
      return offset;
    }
    exports.emptyScalarPosition = emptyScalarPosition;
  }
});

// node_modules/yaml/dist/compose/compose-node.js
var require_compose_node = __commonJS({
  "node_modules/yaml/dist/compose/compose-node.js"(exports) {
    "use strict";
    var Alias = require_Alias();
    var identity = require_identity();
    var composeCollection = require_compose_collection();
    var composeScalar = require_compose_scalar();
    var resolveEnd = require_resolve_end();
    var utilEmptyScalarPosition = require_util_empty_scalar_position();
    var CN = { composeNode, composeEmptyNode };
    function composeNode(ctx, token, props, onError) {
      const atKey = ctx.atKey;
      const { spaceBefore, comment, anchor, tag } = props;
      let node;
      let isSrcToken = true;
      switch (token.type) {
        case "alias":
          node = composeAlias(ctx, token, onError);
          if (anchor || tag)
            onError(token, "ALIAS_PROPS", "An alias node must not specify any properties");
          break;
        case "scalar":
        case "single-quoted-scalar":
        case "double-quoted-scalar":
        case "block-scalar":
          node = composeScalar.composeScalar(ctx, token, tag, onError);
          if (anchor)
            node.anchor = anchor.source.substring(1);
          break;
        case "block-map":
        case "block-seq":
        case "flow-collection":
          try {
            node = composeCollection.composeCollection(CN, ctx, token, props, onError);
            if (anchor)
              node.anchor = anchor.source.substring(1);
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            onError(token, "RESOURCE_EXHAUSTION", message);
          }
          break;
        default: {
          const message = token.type === "error" ? token.message : `Unsupported token (type: ${token.type})`;
          onError(token, "UNEXPECTED_TOKEN", message);
          isSrcToken = false;
        }
      }
      node ?? (node = composeEmptyNode(ctx, token.offset, void 0, null, props, onError));
      if (anchor && node.anchor === "")
        onError(anchor, "BAD_ALIAS", "Anchor cannot be an empty string");
      if (atKey && ctx.options.stringKeys && (!identity.isScalar(node) || typeof node.value !== "string" || node.tag && node.tag !== "tag:yaml.org,2002:str")) {
        const msg = "With stringKeys, all keys must be strings";
        onError(tag ?? token, "NON_STRING_KEY", msg);
      }
      if (spaceBefore)
        node.spaceBefore = true;
      if (comment) {
        if (token.type === "scalar" && token.source === "")
          node.comment = comment;
        else
          node.commentBefore = comment;
      }
      if (ctx.options.keepSourceTokens && isSrcToken)
        node.srcToken = token;
      return node;
    }
    function composeEmptyNode(ctx, offset, before, pos, { spaceBefore, comment, anchor, tag, end }, onError) {
      const token = {
        type: "scalar",
        offset: utilEmptyScalarPosition.emptyScalarPosition(offset, before, pos),
        indent: -1,
        source: ""
      };
      const node = composeScalar.composeScalar(ctx, token, tag, onError);
      if (anchor) {
        node.anchor = anchor.source.substring(1);
        if (node.anchor === "")
          onError(anchor, "BAD_ALIAS", "Anchor cannot be an empty string");
      }
      if (spaceBefore)
        node.spaceBefore = true;
      if (comment) {
        node.comment = comment;
        node.range[2] = end;
      }
      return node;
    }
    function composeAlias({ options }, { offset, source, end }, onError) {
      const alias = new Alias.Alias(source.substring(1));
      if (alias.source === "")
        onError(offset, "BAD_ALIAS", "Alias cannot be an empty string");
      if (alias.source.endsWith(":"))
        onError(offset + source.length - 1, "BAD_ALIAS", "Alias ending in : is ambiguous", true);
      const valueEnd = offset + source.length;
      const re = resolveEnd.resolveEnd(end, valueEnd, options.strict, onError);
      alias.range = [offset, valueEnd, re.offset];
      if (re.comment)
        alias.comment = re.comment;
      return alias;
    }
    exports.composeEmptyNode = composeEmptyNode;
    exports.composeNode = composeNode;
  }
});

// node_modules/yaml/dist/compose/compose-doc.js
var require_compose_doc = __commonJS({
  "node_modules/yaml/dist/compose/compose-doc.js"(exports) {
    "use strict";
    var Document = require_Document();
    var composeNode = require_compose_node();
    var resolveEnd = require_resolve_end();
    var resolveProps = require_resolve_props();
    function composeDoc(options, directives, { offset, start, value, end }, onError) {
      const opts = Object.assign({ _directives: directives }, options);
      const doc = new Document.Document(void 0, opts);
      const ctx = {
        atKey: false,
        atRoot: true,
        directives: doc.directives,
        options: doc.options,
        schema: doc.schema
      };
      const props = resolveProps.resolveProps(start, {
        indicator: "doc-start",
        next: value ?? end?.[0],
        offset,
        onError,
        parentIndent: 0,
        startOnNewline: true
      });
      if (props.found) {
        doc.directives.docStart = true;
        if (value && (value.type === "block-map" || value.type === "block-seq") && !props.hasNewline)
          onError(props.end, "MISSING_CHAR", "Block collection cannot start on same line with directives-end marker");
      }
      doc.contents = value ? composeNode.composeNode(ctx, value, props, onError) : composeNode.composeEmptyNode(ctx, props.end, start, null, props, onError);
      const contentEnd = doc.contents.range[2];
      const re = resolveEnd.resolveEnd(end, contentEnd, false, onError);
      if (re.comment)
        doc.comment = re.comment;
      doc.range = [offset, contentEnd, re.offset];
      return doc;
    }
    exports.composeDoc = composeDoc;
  }
});

// node_modules/yaml/dist/compose/composer.js
var require_composer = __commonJS({
  "node_modules/yaml/dist/compose/composer.js"(exports) {
    "use strict";
    var node_process = __require("process");
    var directives = require_directives();
    var Document = require_Document();
    var errors = require_errors();
    var identity = require_identity();
    var composeDoc = require_compose_doc();
    var resolveEnd = require_resolve_end();
    function getErrorPos(src) {
      if (typeof src === "number")
        return [src, src + 1];
      if (Array.isArray(src))
        return src.length === 2 ? src : [src[0], src[1]];
      const { offset, source } = src;
      return [offset, offset + (typeof source === "string" ? source.length : 1)];
    }
    function parsePrelude(prelude) {
      let comment = "";
      let atComment = false;
      let afterEmptyLine = false;
      for (let i = 0; i < prelude.length; ++i) {
        const source = prelude[i];
        switch (source[0]) {
          case "#":
            comment += (comment === "" ? "" : afterEmptyLine ? "\n\n" : "\n") + (source.substring(1) || " ");
            atComment = true;
            afterEmptyLine = false;
            break;
          case "%":
            if (prelude[i + 1]?.[0] !== "#")
              i += 1;
            atComment = false;
            break;
          default:
            if (!atComment)
              afterEmptyLine = true;
            atComment = false;
        }
      }
      return { comment, afterEmptyLine };
    }
    var Composer = class {
      constructor(options = {}) {
        this.doc = null;
        this.atDirectives = false;
        this.prelude = [];
        this.errors = [];
        this.warnings = [];
        this.onError = (source, code, message, warning) => {
          const pos = getErrorPos(source);
          if (warning)
            this.warnings.push(new errors.YAMLWarning(pos, code, message));
          else
            this.errors.push(new errors.YAMLParseError(pos, code, message));
        };
        this.directives = new directives.Directives({ version: options.version || "1.2" });
        this.options = options;
      }
      decorate(doc, afterDoc) {
        const { comment, afterEmptyLine } = parsePrelude(this.prelude);
        if (comment) {
          const dc = doc.contents;
          if (afterDoc) {
            doc.comment = doc.comment ? `${doc.comment}
${comment}` : comment;
          } else if (afterEmptyLine || doc.directives.docStart || !dc) {
            doc.commentBefore = comment;
          } else if (identity.isCollection(dc) && !dc.flow && dc.items.length > 0) {
            let it = dc.items[0];
            if (identity.isPair(it))
              it = it.key;
            const cb = it.commentBefore;
            it.commentBefore = cb ? `${comment}
${cb}` : comment;
          } else {
            const cb = dc.commentBefore;
            dc.commentBefore = cb ? `${comment}
${cb}` : comment;
          }
        }
        if (afterDoc) {
          for (let i = 0; i < this.errors.length; ++i)
            doc.errors.push(this.errors[i]);
          for (let i = 0; i < this.warnings.length; ++i)
            doc.warnings.push(this.warnings[i]);
        } else {
          doc.errors = this.errors;
          doc.warnings = this.warnings;
        }
        this.prelude = [];
        this.errors = [];
        this.warnings = [];
      }
      /**
       * Current stream status information.
       *
       * Mostly useful at the end of input for an empty stream.
       */
      streamInfo() {
        return {
          comment: parsePrelude(this.prelude).comment,
          directives: this.directives,
          errors: this.errors,
          warnings: this.warnings
        };
      }
      /**
       * Compose tokens into documents.
       *
       * @param forceDoc - If the stream contains no document, still emit a final document including any comments and directives that would be applied to a subsequent document.
       * @param endOffset - Should be set if `forceDoc` is also set, to set the document range end and to indicate errors correctly.
       */
      *compose(tokens, forceDoc = false, endOffset = -1) {
        for (const token of tokens)
          yield* this.next(token);
        yield* this.end(forceDoc, endOffset);
      }
      /** Advance the composer by one CST token. */
      *next(token) {
        if (node_process.env.LOG_STREAM)
          console.dir(token, { depth: null });
        switch (token.type) {
          case "directive":
            this.directives.add(token.source, (offset, message, warning) => {
              const pos = getErrorPos(token);
              pos[0] += offset;
              this.onError(pos, "BAD_DIRECTIVE", message, warning);
            });
            this.prelude.push(token.source);
            this.atDirectives = true;
            break;
          case "document": {
            const doc = composeDoc.composeDoc(this.options, this.directives, token, this.onError);
            if (this.atDirectives && !doc.directives.docStart)
              this.onError(token, "MISSING_CHAR", "Missing directives-end/doc-start indicator line");
            this.decorate(doc, false);
            if (this.doc)
              yield this.doc;
            this.doc = doc;
            this.atDirectives = false;
            break;
          }
          case "byte-order-mark":
          case "space":
            break;
          case "comment":
          case "newline":
            this.prelude.push(token.source);
            break;
          case "error": {
            const msg = token.source ? `${token.message}: ${JSON.stringify(token.source)}` : token.message;
            const error = new errors.YAMLParseError(getErrorPos(token), "UNEXPECTED_TOKEN", msg);
            if (this.atDirectives || !this.doc)
              this.errors.push(error);
            else
              this.doc.errors.push(error);
            break;
          }
          case "doc-end": {
            if (!this.doc) {
              const msg = "Unexpected doc-end without preceding document";
              this.errors.push(new errors.YAMLParseError(getErrorPos(token), "UNEXPECTED_TOKEN", msg));
              break;
            }
            this.doc.directives.docEnd = true;
            const end = resolveEnd.resolveEnd(token.end, token.offset + token.source.length, this.doc.options.strict, this.onError);
            this.decorate(this.doc, true);
            if (end.comment) {
              const dc = this.doc.comment;
              this.doc.comment = dc ? `${dc}
${end.comment}` : end.comment;
            }
            this.doc.range[2] = end.offset;
            break;
          }
          default:
            this.errors.push(new errors.YAMLParseError(getErrorPos(token), "UNEXPECTED_TOKEN", `Unsupported token ${token.type}`));
        }
      }
      /**
       * Call at end of input to yield any remaining document.
       *
       * @param forceDoc - If the stream contains no document, still emit a final document including any comments and directives that would be applied to a subsequent document.
       * @param endOffset - Should be set if `forceDoc` is also set, to set the document range end and to indicate errors correctly.
       */
      *end(forceDoc = false, endOffset = -1) {
        if (this.doc) {
          this.decorate(this.doc, true);
          yield this.doc;
          this.doc = null;
        } else if (forceDoc) {
          const opts = Object.assign({ _directives: this.directives }, this.options);
          const doc = new Document.Document(void 0, opts);
          if (this.atDirectives)
            this.onError(endOffset, "MISSING_CHAR", "Missing directives-end indicator line");
          doc.range = [0, endOffset, endOffset];
          this.decorate(doc, false);
          yield doc;
        }
      }
    };
    exports.Composer = Composer;
  }
});

// node_modules/yaml/dist/parse/cst-scalar.js
var require_cst_scalar = __commonJS({
  "node_modules/yaml/dist/parse/cst-scalar.js"(exports) {
    "use strict";
    var resolveBlockScalar = require_resolve_block_scalar();
    var resolveFlowScalar = require_resolve_flow_scalar();
    var errors = require_errors();
    var stringifyString = require_stringifyString();
    function resolveAsScalar(token, strict = true, onError) {
      if (token) {
        const _onError = (pos, code, message) => {
          const offset = typeof pos === "number" ? pos : Array.isArray(pos) ? pos[0] : pos.offset;
          if (onError)
            onError(offset, code, message);
          else
            throw new errors.YAMLParseError([offset, offset + 1], code, message);
        };
        switch (token.type) {
          case "scalar":
          case "single-quoted-scalar":
          case "double-quoted-scalar":
            return resolveFlowScalar.resolveFlowScalar(token, strict, _onError);
          case "block-scalar":
            return resolveBlockScalar.resolveBlockScalar({ options: { strict } }, token, _onError);
        }
      }
      return null;
    }
    function createScalarToken(value, context) {
      const { implicitKey = false, indent, inFlow = false, offset = -1, type = "PLAIN" } = context;
      const source = stringifyString.stringifyString({ type, value }, {
        implicitKey,
        indent: indent > 0 ? " ".repeat(indent) : "",
        inFlow,
        options: { blockQuote: true, lineWidth: -1 }
      });
      const end = context.end ?? [
        { type: "newline", offset: -1, indent, source: "\n" }
      ];
      switch (source[0]) {
        case "|":
        case ">": {
          const he = source.indexOf("\n");
          const head = source.substring(0, he);
          const body = source.substring(he + 1) + "\n";
          const props = [
            { type: "block-scalar-header", offset, indent, source: head }
          ];
          if (!addEndtoBlockProps(props, end))
            props.push({ type: "newline", offset: -1, indent, source: "\n" });
          return { type: "block-scalar", offset, indent, props, source: body };
        }
        case '"':
          return { type: "double-quoted-scalar", offset, indent, source, end };
        case "'":
          return { type: "single-quoted-scalar", offset, indent, source, end };
        default:
          return { type: "scalar", offset, indent, source, end };
      }
    }
    function setScalarValue(token, value, context = {}) {
      let { afterKey = false, implicitKey = false, inFlow = false, type } = context;
      let indent = "indent" in token ? token.indent : null;
      if (afterKey && typeof indent === "number")
        indent += 2;
      if (!type)
        switch (token.type) {
          case "single-quoted-scalar":
            type = "QUOTE_SINGLE";
            break;
          case "double-quoted-scalar":
            type = "QUOTE_DOUBLE";
            break;
          case "block-scalar": {
            const header = token.props[0];
            if (header.type !== "block-scalar-header")
              throw new Error("Invalid block scalar header");
            type = header.source[0] === ">" ? "BLOCK_FOLDED" : "BLOCK_LITERAL";
            break;
          }
          default:
            type = "PLAIN";
        }
      const source = stringifyString.stringifyString({ type, value }, {
        implicitKey: implicitKey || indent === null,
        indent: indent !== null && indent > 0 ? " ".repeat(indent) : "",
        inFlow,
        options: { blockQuote: true, lineWidth: -1 }
      });
      switch (source[0]) {
        case "|":
        case ">":
          setBlockScalarValue(token, source);
          break;
        case '"':
          setFlowScalarValue(token, source, "double-quoted-scalar");
          break;
        case "'":
          setFlowScalarValue(token, source, "single-quoted-scalar");
          break;
        default:
          setFlowScalarValue(token, source, "scalar");
      }
    }
    function setBlockScalarValue(token, source) {
      const he = source.indexOf("\n");
      const head = source.substring(0, he);
      const body = source.substring(he + 1) + "\n";
      if (token.type === "block-scalar") {
        const header = token.props[0];
        if (header.type !== "block-scalar-header")
          throw new Error("Invalid block scalar header");
        header.source = head;
        token.source = body;
      } else {
        const { offset } = token;
        const indent = "indent" in token ? token.indent : -1;
        const props = [
          { type: "block-scalar-header", offset, indent, source: head }
        ];
        if (!addEndtoBlockProps(props, "end" in token ? token.end : void 0))
          props.push({ type: "newline", offset: -1, indent, source: "\n" });
        for (const key of Object.keys(token))
          if (key !== "type" && key !== "offset")
            delete token[key];
        Object.assign(token, { type: "block-scalar", indent, props, source: body });
      }
    }
    function addEndtoBlockProps(props, end) {
      if (end)
        for (const st of end)
          switch (st.type) {
            case "space":
            case "comment":
              props.push(st);
              break;
            case "newline":
              props.push(st);
              return true;
          }
      return false;
    }
    function setFlowScalarValue(token, source, type) {
      switch (token.type) {
        case "scalar":
        case "double-quoted-scalar":
        case "single-quoted-scalar":
          token.type = type;
          token.source = source;
          break;
        case "block-scalar": {
          const end = token.props.slice(1);
          let oa = source.length;
          if (token.props[0].type === "block-scalar-header")
            oa -= token.props[0].source.length;
          for (const tok of end)
            tok.offset += oa;
          delete token.props;
          Object.assign(token, { type, source, end });
          break;
        }
        case "block-map":
        case "block-seq": {
          const offset = token.offset + source.length;
          const nl = { type: "newline", offset, indent: token.indent, source: "\n" };
          delete token.items;
          Object.assign(token, { type, source, end: [nl] });
          break;
        }
        default: {
          const indent = "indent" in token ? token.indent : -1;
          const end = "end" in token && Array.isArray(token.end) ? token.end.filter((st) => st.type === "space" || st.type === "comment" || st.type === "newline") : [];
          for (const key of Object.keys(token))
            if (key !== "type" && key !== "offset")
              delete token[key];
          Object.assign(token, { type, indent, source, end });
        }
      }
    }
    exports.createScalarToken = createScalarToken;
    exports.resolveAsScalar = resolveAsScalar;
    exports.setScalarValue = setScalarValue;
  }
});

// node_modules/yaml/dist/parse/cst-stringify.js
var require_cst_stringify = __commonJS({
  "node_modules/yaml/dist/parse/cst-stringify.js"(exports) {
    "use strict";
    var stringify = (cst) => "type" in cst ? stringifyToken(cst) : stringifyItem(cst);
    function stringifyToken(token) {
      switch (token.type) {
        case "block-scalar": {
          let res = "";
          for (const tok of token.props)
            res += stringifyToken(tok);
          return res + token.source;
        }
        case "block-map":
        case "block-seq": {
          let res = "";
          for (const item of token.items)
            res += stringifyItem(item);
          return res;
        }
        case "flow-collection": {
          let res = token.start.source;
          for (const item of token.items)
            res += stringifyItem(item);
          for (const st of token.end)
            res += st.source;
          return res;
        }
        case "document": {
          let res = stringifyItem(token);
          if (token.end)
            for (const st of token.end)
              res += st.source;
          return res;
        }
        default: {
          let res = token.source;
          if ("end" in token && token.end)
            for (const st of token.end)
              res += st.source;
          return res;
        }
      }
    }
    function stringifyItem({ start, key, sep: sep2, value }) {
      let res = "";
      for (const st of start)
        res += st.source;
      if (key)
        res += stringifyToken(key);
      if (sep2)
        for (const st of sep2)
          res += st.source;
      if (value)
        res += stringifyToken(value);
      return res;
    }
    exports.stringify = stringify;
  }
});

// node_modules/yaml/dist/parse/cst-visit.js
var require_cst_visit = __commonJS({
  "node_modules/yaml/dist/parse/cst-visit.js"(exports) {
    "use strict";
    var BREAK = /* @__PURE__ */ Symbol("break visit");
    var SKIP = /* @__PURE__ */ Symbol("skip children");
    var REMOVE = /* @__PURE__ */ Symbol("remove item");
    function visit(cst, visitor) {
      if ("type" in cst && cst.type === "document")
        cst = { start: cst.start, value: cst.value };
      _visit(Object.freeze([]), cst, visitor);
    }
    visit.BREAK = BREAK;
    visit.SKIP = SKIP;
    visit.REMOVE = REMOVE;
    visit.itemAtPath = (cst, path) => {
      let item = cst;
      for (const [field, index] of path) {
        const tok = item?.[field];
        if (tok && "items" in tok) {
          item = tok.items[index];
        } else
          return void 0;
      }
      return item;
    };
    visit.parentCollection = (cst, path) => {
      const parent = visit.itemAtPath(cst, path.slice(0, -1));
      const field = path[path.length - 1][0];
      const coll = parent?.[field];
      if (coll && "items" in coll)
        return coll;
      throw new Error("Parent collection not found");
    };
    function _visit(path, item, visitor) {
      let ctrl = visitor(item, path);
      if (typeof ctrl === "symbol")
        return ctrl;
      for (const field of ["key", "value"]) {
        const token = item[field];
        if (token && "items" in token) {
          for (let i = 0; i < token.items.length; ++i) {
            const ci = _visit(Object.freeze(path.concat([[field, i]])), token.items[i], visitor);
            if (typeof ci === "number")
              i = ci - 1;
            else if (ci === BREAK)
              return BREAK;
            else if (ci === REMOVE) {
              token.items.splice(i, 1);
              i -= 1;
            }
          }
          if (typeof ctrl === "function" && field === "key")
            ctrl = ctrl(item, path);
        }
      }
      return typeof ctrl === "function" ? ctrl(item, path) : ctrl;
    }
    exports.visit = visit;
  }
});

// node_modules/yaml/dist/parse/cst.js
var require_cst = __commonJS({
  "node_modules/yaml/dist/parse/cst.js"(exports) {
    "use strict";
    var cstScalar = require_cst_scalar();
    var cstStringify = require_cst_stringify();
    var cstVisit = require_cst_visit();
    var BOM = "\uFEFF";
    var DOCUMENT = "";
    var FLOW_END = "";
    var SCALAR = "";
    var isCollection = (token) => !!token && "items" in token;
    var isScalar = (token) => !!token && (token.type === "scalar" || token.type === "single-quoted-scalar" || token.type === "double-quoted-scalar" || token.type === "block-scalar");
    function prettyToken(token) {
      switch (token) {
        case BOM:
          return "<BOM>";
        case DOCUMENT:
          return "<DOC>";
        case FLOW_END:
          return "<FLOW_END>";
        case SCALAR:
          return "<SCALAR>";
        default:
          return JSON.stringify(token);
      }
    }
    function tokenType(source) {
      switch (source) {
        case BOM:
          return "byte-order-mark";
        case DOCUMENT:
          return "doc-mode";
        case FLOW_END:
          return "flow-error-end";
        case SCALAR:
          return "scalar";
        case "---":
          return "doc-start";
        case "...":
          return "doc-end";
        case "":
        case "\n":
        case "\r\n":
          return "newline";
        case "-":
          return "seq-item-ind";
        case "?":
          return "explicit-key-ind";
        case ":":
          return "map-value-ind";
        case "{":
          return "flow-map-start";
        case "}":
          return "flow-map-end";
        case "[":
          return "flow-seq-start";
        case "]":
          return "flow-seq-end";
        case ",":
          return "comma";
      }
      switch (source[0]) {
        case " ":
        case "	":
          return "space";
        case "#":
          return "comment";
        case "%":
          return "directive-line";
        case "*":
          return "alias";
        case "&":
          return "anchor";
        case "!":
          return "tag";
        case "'":
          return "single-quoted-scalar";
        case '"':
          return "double-quoted-scalar";
        case "|":
        case ">":
          return "block-scalar-header";
      }
      return null;
    }
    exports.createScalarToken = cstScalar.createScalarToken;
    exports.resolveAsScalar = cstScalar.resolveAsScalar;
    exports.setScalarValue = cstScalar.setScalarValue;
    exports.stringify = cstStringify.stringify;
    exports.visit = cstVisit.visit;
    exports.BOM = BOM;
    exports.DOCUMENT = DOCUMENT;
    exports.FLOW_END = FLOW_END;
    exports.SCALAR = SCALAR;
    exports.isCollection = isCollection;
    exports.isScalar = isScalar;
    exports.prettyToken = prettyToken;
    exports.tokenType = tokenType;
  }
});

// node_modules/yaml/dist/parse/lexer.js
var require_lexer = __commonJS({
  "node_modules/yaml/dist/parse/lexer.js"(exports) {
    "use strict";
    var cst = require_cst();
    function isEmpty(ch) {
      switch (ch) {
        case void 0:
        case " ":
        case "\n":
        case "\r":
        case "	":
          return true;
        default:
          return false;
      }
    }
    var hexDigits = new Set("0123456789ABCDEFabcdef");
    var tagChars = new Set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-#;/?:@&=+$_.!~*'()");
    var flowIndicatorChars = new Set(",[]{}");
    var invalidAnchorChars = new Set(" ,[]{}\n\r	");
    var isNotAnchorChar = (ch) => !ch || invalidAnchorChars.has(ch);
    var Lexer = class {
      constructor() {
        this.atEnd = false;
        this.blockScalarIndent = -1;
        this.blockScalarKeep = false;
        this.buffer = "";
        this.flowKey = false;
        this.flowLevel = 0;
        this.indentNext = 0;
        this.indentValue = 0;
        this.lineEndPos = null;
        this.next = null;
        this.pos = 0;
      }
      /**
       * Generate YAML tokens from the `source` string. If `incomplete`,
       * a part of the last line may be left as a buffer for the next call.
       *
       * @returns A generator of lexical tokens
       */
      *lex(source, incomplete = false) {
        if (source) {
          if (typeof source !== "string")
            throw TypeError("source is not a string");
          this.buffer = this.buffer ? this.buffer + source : source;
          this.lineEndPos = null;
        }
        this.atEnd = !incomplete;
        let next = this.next ?? "stream";
        while (next && (incomplete || this.hasChars(1)))
          next = yield* this.parseNext(next);
      }
      atLineEnd() {
        let i = this.pos;
        let ch = this.buffer[i];
        while (ch === " " || ch === "	")
          ch = this.buffer[++i];
        if (!ch || ch === "#" || ch === "\n")
          return true;
        if (ch === "\r")
          return this.buffer[i + 1] === "\n";
        return false;
      }
      charAt(n) {
        return this.buffer[this.pos + n];
      }
      continueScalar(offset) {
        let ch = this.buffer[offset];
        if (this.indentNext > 0) {
          let indent = 0;
          while (ch === " ")
            ch = this.buffer[++indent + offset];
          if (ch === "\r") {
            const next = this.buffer[indent + offset + 1];
            if (next === "\n" || !next && !this.atEnd)
              return offset + indent + 1;
          }
          return ch === "\n" || indent >= this.indentNext || !ch && !this.atEnd ? offset + indent : -1;
        }
        if (ch === "-" || ch === ".") {
          const dt = this.buffer.substr(offset, 3);
          if ((dt === "---" || dt === "...") && isEmpty(this.buffer[offset + 3]))
            return -1;
        }
        return offset;
      }
      getLine() {
        let end = this.lineEndPos;
        if (typeof end !== "number" || end !== -1 && end < this.pos) {
          end = this.buffer.indexOf("\n", this.pos);
          this.lineEndPos = end;
        }
        if (end === -1)
          return this.atEnd ? this.buffer.substring(this.pos) : null;
        if (this.buffer[end - 1] === "\r")
          end -= 1;
        return this.buffer.substring(this.pos, end);
      }
      hasChars(n) {
        return this.pos + n <= this.buffer.length;
      }
      setNext(state) {
        this.buffer = this.buffer.substring(this.pos);
        this.pos = 0;
        this.lineEndPos = null;
        this.next = state;
        return null;
      }
      peek(n) {
        return this.buffer.substr(this.pos, n);
      }
      *parseNext(next) {
        switch (next) {
          case "stream":
            return yield* this.parseStream();
          case "line-start":
            return yield* this.parseLineStart();
          case "block-start":
            return yield* this.parseBlockStart();
          case "doc":
            return yield* this.parseDocument();
          case "flow":
            return yield* this.parseFlowCollection();
          case "quoted-scalar":
            return yield* this.parseQuotedScalar();
          case "block-scalar":
            return yield* this.parseBlockScalar();
          case "plain-scalar":
            return yield* this.parsePlainScalar();
        }
      }
      *parseStream() {
        let line = this.getLine();
        if (line === null)
          return this.setNext("stream");
        if (line[0] === cst.BOM) {
          yield* this.pushCount(1);
          line = line.substring(1);
        }
        if (line[0] === "%") {
          let dirEnd = line.length;
          let cs = line.indexOf("#");
          while (cs !== -1) {
            const ch = line[cs - 1];
            if (ch === " " || ch === "	") {
              dirEnd = cs - 1;
              break;
            } else {
              cs = line.indexOf("#", cs + 1);
            }
          }
          while (true) {
            const ch = line[dirEnd - 1];
            if (ch === " " || ch === "	")
              dirEnd -= 1;
            else
              break;
          }
          const n = (yield* this.pushCount(dirEnd)) + (yield* this.pushSpaces(true));
          yield* this.pushCount(line.length - n);
          this.pushNewline();
          return "stream";
        }
        if (this.atLineEnd()) {
          const sp = yield* this.pushSpaces(true);
          yield* this.pushCount(line.length - sp);
          yield* this.pushNewline();
          return "stream";
        }
        yield cst.DOCUMENT;
        return yield* this.parseLineStart();
      }
      *parseLineStart() {
        const ch = this.charAt(0);
        if (!ch && !this.atEnd)
          return this.setNext("line-start");
        if (ch === "-" || ch === ".") {
          if (!this.atEnd && !this.hasChars(4))
            return this.setNext("line-start");
          const s = this.peek(3);
          if ((s === "---" || s === "...") && isEmpty(this.charAt(3))) {
            yield* this.pushCount(3);
            this.indentValue = 0;
            this.indentNext = 0;
            return s === "---" ? "doc" : "stream";
          }
        }
        this.indentValue = yield* this.pushSpaces(false);
        if (this.indentNext > this.indentValue && !isEmpty(this.charAt(1)))
          this.indentNext = this.indentValue;
        return yield* this.parseBlockStart();
      }
      *parseBlockStart() {
        const [ch0, ch1] = this.peek(2);
        if (!ch1 && !this.atEnd)
          return this.setNext("block-start");
        if ((ch0 === "-" || ch0 === "?" || ch0 === ":") && isEmpty(ch1)) {
          const n = (yield* this.pushCount(1)) + (yield* this.pushSpaces(true));
          this.indentNext = this.indentValue + 1;
          this.indentValue += n;
          return "block-start";
        }
        return "doc";
      }
      *parseDocument() {
        yield* this.pushSpaces(true);
        const line = this.getLine();
        if (line === null)
          return this.setNext("doc");
        let n = yield* this.pushIndicators();
        switch (line[n]) {
          case "#":
            yield* this.pushCount(line.length - n);
          // fallthrough
          case void 0:
            yield* this.pushNewline();
            return yield* this.parseLineStart();
          case "{":
          case "[":
            yield* this.pushCount(1);
            this.flowKey = false;
            this.flowLevel = 1;
            return "flow";
          case "}":
          case "]":
            yield* this.pushCount(1);
            return "doc";
          case "*":
            yield* this.pushUntil(isNotAnchorChar);
            return "doc";
          case '"':
          case "'":
            return yield* this.parseQuotedScalar();
          case "|":
          case ">":
            n += yield* this.parseBlockScalarHeader();
            n += yield* this.pushSpaces(true);
            yield* this.pushCount(line.length - n);
            yield* this.pushNewline();
            return yield* this.parseBlockScalar();
          default:
            return yield* this.parsePlainScalar();
        }
      }
      *parseFlowCollection() {
        let nl, sp;
        let indent = -1;
        do {
          nl = yield* this.pushNewline();
          if (nl > 0) {
            sp = yield* this.pushSpaces(false);
            this.indentValue = indent = sp;
          } else {
            sp = 0;
          }
          sp += yield* this.pushSpaces(true);
        } while (nl + sp > 0);
        const line = this.getLine();
        if (line === null)
          return this.setNext("flow");
        if (indent !== -1 && indent < this.indentNext && line[0] !== "#" || indent === 0 && (line.startsWith("---") || line.startsWith("...")) && isEmpty(line[3])) {
          const atFlowEndMarker = indent === this.indentNext - 1 && this.flowLevel === 1 && (line[0] === "]" || line[0] === "}");
          if (!atFlowEndMarker) {
            this.flowLevel = 0;
            yield cst.FLOW_END;
            return yield* this.parseLineStart();
          }
        }
        let n = 0;
        while (line[n] === ",") {
          n += yield* this.pushCount(1);
          n += yield* this.pushSpaces(true);
          this.flowKey = false;
        }
        n += yield* this.pushIndicators();
        switch (line[n]) {
          case void 0:
            return "flow";
          case "#":
            yield* this.pushCount(line.length - n);
            return "flow";
          case "{":
          case "[":
            yield* this.pushCount(1);
            this.flowKey = false;
            this.flowLevel += 1;
            return "flow";
          case "}":
          case "]":
            yield* this.pushCount(1);
            this.flowKey = true;
            this.flowLevel -= 1;
            return this.flowLevel ? "flow" : "doc";
          case "*":
            yield* this.pushUntil(isNotAnchorChar);
            return "flow";
          case '"':
          case "'":
            this.flowKey = true;
            return yield* this.parseQuotedScalar();
          case ":": {
            const next = this.charAt(1);
            if (this.flowKey || isEmpty(next) || next === ",") {
              this.flowKey = false;
              yield* this.pushCount(1);
              yield* this.pushSpaces(true);
              return "flow";
            }
          }
          // fallthrough
          default:
            this.flowKey = false;
            return yield* this.parsePlainScalar();
        }
      }
      *parseQuotedScalar() {
        const quote = this.charAt(0);
        let end = this.buffer.indexOf(quote, this.pos + 1);
        if (quote === "'") {
          while (end !== -1 && this.buffer[end + 1] === "'")
            end = this.buffer.indexOf("'", end + 2);
        } else {
          while (end !== -1) {
            let n = 0;
            while (this.buffer[end - 1 - n] === "\\")
              n += 1;
            if (n % 2 === 0)
              break;
            end = this.buffer.indexOf('"', end + 1);
          }
        }
        const qb = this.buffer.substring(0, end);
        let nl = qb.indexOf("\n", this.pos);
        if (nl !== -1) {
          while (nl !== -1) {
            const cs = this.continueScalar(nl + 1);
            if (cs === -1)
              break;
            nl = qb.indexOf("\n", cs);
          }
          if (nl !== -1) {
            end = nl - (qb[nl - 1] === "\r" ? 2 : 1);
          }
        }
        if (end === -1) {
          if (!this.atEnd)
            return this.setNext("quoted-scalar");
          end = this.buffer.length;
        }
        yield* this.pushToIndex(end + 1, false);
        return this.flowLevel ? "flow" : "doc";
      }
      *parseBlockScalarHeader() {
        this.blockScalarIndent = -1;
        this.blockScalarKeep = false;
        let i = this.pos;
        while (true) {
          const ch = this.buffer[++i];
          if (ch === "+")
            this.blockScalarKeep = true;
          else if (ch > "0" && ch <= "9")
            this.blockScalarIndent = Number(ch) - 1;
          else if (ch !== "-")
            break;
        }
        return yield* this.pushUntil((ch) => isEmpty(ch) || ch === "#");
      }
      *parseBlockScalar() {
        let nl = this.pos - 1;
        let indent = 0;
        let ch;
        loop: for (let i2 = this.pos; ch = this.buffer[i2]; ++i2) {
          switch (ch) {
            case " ":
              indent += 1;
              break;
            case "\n":
              nl = i2;
              indent = 0;
              break;
            case "\r": {
              const next = this.buffer[i2 + 1];
              if (!next && !this.atEnd)
                return this.setNext("block-scalar");
              if (next === "\n")
                break;
            }
            // fallthrough
            default:
              break loop;
          }
        }
        if (!ch && !this.atEnd)
          return this.setNext("block-scalar");
        if (indent >= this.indentNext) {
          if (this.blockScalarIndent === -1)
            this.indentNext = indent;
          else {
            this.indentNext = this.blockScalarIndent + (this.indentNext === 0 ? 1 : this.indentNext);
          }
          do {
            const cs = this.continueScalar(nl + 1);
            if (cs === -1)
              break;
            nl = this.buffer.indexOf("\n", cs);
          } while (nl !== -1);
          if (nl === -1) {
            if (!this.atEnd)
              return this.setNext("block-scalar");
            nl = this.buffer.length;
          }
        }
        let i = nl + 1;
        ch = this.buffer[i];
        while (ch === " ")
          ch = this.buffer[++i];
        if (ch === "	") {
          while (ch === "	" || ch === " " || ch === "\r" || ch === "\n")
            ch = this.buffer[++i];
          nl = i - 1;
        } else if (!this.blockScalarKeep) {
          do {
            let i2 = nl - 1;
            let ch2 = this.buffer[i2];
            if (ch2 === "\r")
              ch2 = this.buffer[--i2];
            const lastChar = i2;
            while (ch2 === " ")
              ch2 = this.buffer[--i2];
            if (ch2 === "\n" && i2 >= this.pos && i2 + 1 + indent > lastChar)
              nl = i2;
            else
              break;
          } while (true);
        }
        yield cst.SCALAR;
        yield* this.pushToIndex(nl + 1, true);
        return yield* this.parseLineStart();
      }
      *parsePlainScalar() {
        const inFlow = this.flowLevel > 0;
        let end = this.pos - 1;
        let i = this.pos - 1;
        let ch;
        while (ch = this.buffer[++i]) {
          if (ch === ":") {
            const next = this.buffer[i + 1];
            if (isEmpty(next) || inFlow && flowIndicatorChars.has(next))
              break;
            end = i;
          } else if (isEmpty(ch)) {
            let next = this.buffer[i + 1];
            if (ch === "\r") {
              if (next === "\n") {
                i += 1;
                ch = "\n";
                next = this.buffer[i + 1];
              } else
                end = i;
            }
            if (next === "#" || inFlow && flowIndicatorChars.has(next))
              break;
            if (ch === "\n") {
              const cs = this.continueScalar(i + 1);
              if (cs === -1)
                break;
              i = Math.max(i, cs - 2);
            }
          } else {
            if (inFlow && flowIndicatorChars.has(ch))
              break;
            end = i;
          }
        }
        if (!ch && !this.atEnd)
          return this.setNext("plain-scalar");
        yield cst.SCALAR;
        yield* this.pushToIndex(end + 1, true);
        return inFlow ? "flow" : "doc";
      }
      *pushCount(n) {
        if (n > 0) {
          yield this.buffer.substr(this.pos, n);
          this.pos += n;
          return n;
        }
        return 0;
      }
      *pushToIndex(i, allowEmpty) {
        const s = this.buffer.slice(this.pos, i);
        if (s) {
          yield s;
          this.pos += s.length;
          return s.length;
        } else if (allowEmpty)
          yield "";
        return 0;
      }
      *pushIndicators() {
        let n = 0;
        loop: while (true) {
          switch (this.charAt(0)) {
            case "!":
              n += yield* this.pushTag();
              n += yield* this.pushSpaces(true);
              continue loop;
            case "&":
              n += yield* this.pushUntil(isNotAnchorChar);
              n += yield* this.pushSpaces(true);
              continue loop;
            case "-":
            // this is an error
            case "?":
            // this is an error outside flow collections
            case ":": {
              const inFlow = this.flowLevel > 0;
              const ch1 = this.charAt(1);
              if (isEmpty(ch1) || inFlow && flowIndicatorChars.has(ch1)) {
                if (!inFlow)
                  this.indentNext = this.indentValue + 1;
                else if (this.flowKey)
                  this.flowKey = false;
                n += yield* this.pushCount(1);
                n += yield* this.pushSpaces(true);
                continue loop;
              }
            }
          }
          break loop;
        }
        return n;
      }
      *pushTag() {
        if (this.charAt(1) === "<") {
          let i = this.pos + 2;
          let ch = this.buffer[i];
          while (!isEmpty(ch) && ch !== ">")
            ch = this.buffer[++i];
          return yield* this.pushToIndex(ch === ">" ? i + 1 : i, false);
        } else {
          let i = this.pos + 1;
          let ch = this.buffer[i];
          while (ch) {
            if (tagChars.has(ch))
              ch = this.buffer[++i];
            else if (ch === "%" && hexDigits.has(this.buffer[i + 1]) && hexDigits.has(this.buffer[i + 2])) {
              ch = this.buffer[i += 3];
            } else
              break;
          }
          return yield* this.pushToIndex(i, false);
        }
      }
      *pushNewline() {
        const ch = this.buffer[this.pos];
        if (ch === "\n")
          return yield* this.pushCount(1);
        else if (ch === "\r" && this.charAt(1) === "\n")
          return yield* this.pushCount(2);
        else
          return 0;
      }
      *pushSpaces(allowTabs) {
        let i = this.pos - 1;
        let ch;
        do {
          ch = this.buffer[++i];
        } while (ch === " " || allowTabs && ch === "	");
        const n = i - this.pos;
        if (n > 0) {
          yield this.buffer.substr(this.pos, n);
          this.pos = i;
        }
        return n;
      }
      *pushUntil(test) {
        let i = this.pos;
        let ch = this.buffer[i];
        while (!test(ch))
          ch = this.buffer[++i];
        return yield* this.pushToIndex(i, false);
      }
    };
    exports.Lexer = Lexer;
  }
});

// node_modules/yaml/dist/parse/line-counter.js
var require_line_counter = __commonJS({
  "node_modules/yaml/dist/parse/line-counter.js"(exports) {
    "use strict";
    var LineCounter = class {
      constructor() {
        this.lineStarts = [];
        this.addNewLine = (offset) => this.lineStarts.push(offset);
        this.linePos = (offset) => {
          let low = 0;
          let high = this.lineStarts.length;
          while (low < high) {
            const mid = low + high >> 1;
            if (this.lineStarts[mid] < offset)
              low = mid + 1;
            else
              high = mid;
          }
          if (this.lineStarts[low] === offset)
            return { line: low + 1, col: 1 };
          if (low === 0)
            return { line: 0, col: offset };
          const start = this.lineStarts[low - 1];
          return { line: low, col: offset - start + 1 };
        };
      }
    };
    exports.LineCounter = LineCounter;
  }
});

// node_modules/yaml/dist/parse/parser.js
var require_parser = __commonJS({
  "node_modules/yaml/dist/parse/parser.js"(exports) {
    "use strict";
    var node_process = __require("process");
    var cst = require_cst();
    var lexer = require_lexer();
    function includesToken(list, type) {
      for (let i = 0; i < list.length; ++i)
        if (list[i].type === type)
          return true;
      return false;
    }
    function findNonEmptyIndex(list) {
      for (let i = 0; i < list.length; ++i) {
        switch (list[i].type) {
          case "space":
          case "comment":
          case "newline":
            break;
          default:
            return i;
        }
      }
      return -1;
    }
    function isFlowToken(token) {
      switch (token?.type) {
        case "alias":
        case "scalar":
        case "single-quoted-scalar":
        case "double-quoted-scalar":
        case "flow-collection":
          return true;
        default:
          return false;
      }
    }
    function getPrevProps(parent) {
      switch (parent.type) {
        case "document":
          return parent.start;
        case "block-map": {
          const it = parent.items[parent.items.length - 1];
          return it.sep ?? it.start;
        }
        case "block-seq":
          return parent.items[parent.items.length - 1].start;
        /* istanbul ignore next should not happen */
        default:
          return [];
      }
    }
    function getFirstKeyStartProps(prev) {
      if (prev.length === 0)
        return [];
      let i = prev.length;
      loop: while (--i >= 0) {
        switch (prev[i].type) {
          case "doc-start":
          case "explicit-key-ind":
          case "map-value-ind":
          case "seq-item-ind":
          case "newline":
            break loop;
        }
      }
      while (prev[++i]?.type === "space") {
      }
      return prev.splice(i, prev.length);
    }
    function arrayPushArray(target, source) {
      if (source.length < 1e5)
        Array.prototype.push.apply(target, source);
      else
        for (let i = 0; i < source.length; ++i)
          target.push(source[i]);
    }
    function fixFlowSeqItems(fc) {
      if (fc.start.type === "flow-seq-start") {
        for (const it of fc.items) {
          if (it.sep && !it.value && !includesToken(it.start, "explicit-key-ind") && !includesToken(it.sep, "map-value-ind")) {
            if (it.key)
              it.value = it.key;
            delete it.key;
            if (isFlowToken(it.value)) {
              if (it.value.end)
                arrayPushArray(it.value.end, it.sep);
              else
                it.value.end = it.sep;
            } else
              arrayPushArray(it.start, it.sep);
            delete it.sep;
          }
        }
      }
    }
    var Parser = class {
      /**
       * @param onNewLine - If defined, called separately with the start position of
       *   each new line (in `parse()`, including the start of input).
       */
      constructor(onNewLine) {
        this.atNewLine = true;
        this.atScalar = false;
        this.indent = 0;
        this.offset = 0;
        this.onKeyLine = false;
        this.stack = [];
        this.source = "";
        this.type = "";
        this.lexer = new lexer.Lexer();
        this.onNewLine = onNewLine;
      }
      /**
       * Parse `source` as a YAML stream.
       * If `incomplete`, a part of the last line may be left as a buffer for the next call.
       *
       * Errors are not thrown, but yielded as `{ type: 'error', message }` tokens.
       *
       * @returns A generator of tokens representing each directive, document, and other structure.
       */
      *parse(source, incomplete = false) {
        if (this.onNewLine && this.offset === 0)
          this.onNewLine(0);
        for (const lexeme of this.lexer.lex(source, incomplete))
          yield* this.next(lexeme);
        if (!incomplete)
          yield* this.end();
      }
      /**
       * Advance the parser by the `source` of one lexical token.
       */
      *next(source) {
        this.source = source;
        if (node_process.env.LOG_TOKENS)
          console.log("|", cst.prettyToken(source));
        if (this.atScalar) {
          this.atScalar = false;
          yield* this.step();
          this.offset += source.length;
          return;
        }
        const type = cst.tokenType(source);
        if (!type) {
          const message = `Not a YAML token: ${source}`;
          yield* this.pop({ type: "error", offset: this.offset, message, source });
          this.offset += source.length;
        } else if (type === "scalar") {
          this.atNewLine = false;
          this.atScalar = true;
          this.type = "scalar";
        } else {
          this.type = type;
          yield* this.step();
          switch (type) {
            case "newline":
              this.atNewLine = true;
              this.indent = 0;
              if (this.onNewLine)
                this.onNewLine(this.offset + source.length);
              break;
            case "space":
              if (this.atNewLine && source[0] === " ")
                this.indent += source.length;
              break;
            case "explicit-key-ind":
            case "map-value-ind":
            case "seq-item-ind":
              if (this.atNewLine)
                this.indent += source.length;
              break;
            case "doc-mode":
            case "flow-error-end":
              return;
            default:
              this.atNewLine = false;
          }
          this.offset += source.length;
        }
      }
      /** Call at end of input to push out any remaining constructions */
      *end() {
        while (this.stack.length > 0)
          yield* this.pop();
      }
      get sourceToken() {
        const st = {
          type: this.type,
          offset: this.offset,
          indent: this.indent,
          source: this.source
        };
        return st;
      }
      *step() {
        const top = this.peek(1);
        if (this.type === "doc-end" && top?.type !== "doc-end") {
          while (this.stack.length > 0)
            yield* this.pop();
          this.stack.push({
            type: "doc-end",
            offset: this.offset,
            source: this.source
          });
          return;
        }
        if (!top)
          return yield* this.stream();
        switch (top.type) {
          case "document":
            return yield* this.document(top);
          case "alias":
          case "scalar":
          case "single-quoted-scalar":
          case "double-quoted-scalar":
            return yield* this.scalar(top);
          case "block-scalar":
            return yield* this.blockScalar(top);
          case "block-map":
            return yield* this.blockMap(top);
          case "block-seq":
            return yield* this.blockSequence(top);
          case "flow-collection":
            return yield* this.flowCollection(top);
          case "doc-end":
            return yield* this.documentEnd(top);
        }
        yield* this.pop();
      }
      peek(n) {
        return this.stack[this.stack.length - n];
      }
      *pop(error) {
        const token = error ?? this.stack.pop();
        if (!token) {
          const message = "Tried to pop an empty stack";
          yield { type: "error", offset: this.offset, source: "", message };
        } else if (this.stack.length === 0) {
          yield token;
        } else {
          const top = this.peek(1);
          if (token.type === "block-scalar") {
            token.indent = "indent" in top ? top.indent : 0;
          } else if (token.type === "flow-collection" && top.type === "document") {
            token.indent = 0;
          }
          if (token.type === "flow-collection")
            fixFlowSeqItems(token);
          switch (top.type) {
            case "document":
              top.value = token;
              break;
            case "block-scalar":
              top.props.push(token);
              break;
            case "block-map": {
              const it = top.items[top.items.length - 1];
              if (it.value) {
                top.items.push({ start: [], key: token, sep: [] });
                this.onKeyLine = true;
                return;
              } else if (it.sep) {
                it.value = token;
              } else {
                Object.assign(it, { key: token, sep: [] });
                this.onKeyLine = !it.explicitKey;
                return;
              }
              break;
            }
            case "block-seq": {
              const it = top.items[top.items.length - 1];
              if (it.value)
                top.items.push({ start: [], value: token });
              else
                it.value = token;
              break;
            }
            case "flow-collection": {
              const it = top.items[top.items.length - 1];
              if (!it || it.value)
                top.items.push({ start: [], key: token, sep: [] });
              else if (it.sep)
                it.value = token;
              else
                Object.assign(it, { key: token, sep: [] });
              return;
            }
            /* istanbul ignore next should not happen */
            default:
              yield* this.pop();
              yield* this.pop(token);
          }
          if ((top.type === "document" || top.type === "block-map" || top.type === "block-seq") && (token.type === "block-map" || token.type === "block-seq")) {
            const last = token.items[token.items.length - 1];
            if (last && !last.sep && !last.value && last.start.length > 0 && findNonEmptyIndex(last.start) === -1 && (token.indent === 0 || last.start.every((st) => st.type !== "comment" || st.indent < token.indent))) {
              if (top.type === "document")
                top.end = last.start;
              else
                top.items.push({ start: last.start });
              token.items.splice(-1, 1);
            }
          }
        }
      }
      *stream() {
        switch (this.type) {
          case "directive-line":
            yield { type: "directive", offset: this.offset, source: this.source };
            return;
          case "byte-order-mark":
          case "space":
          case "comment":
          case "newline":
            yield this.sourceToken;
            return;
          case "doc-mode":
          case "doc-start": {
            const doc = {
              type: "document",
              offset: this.offset,
              start: []
            };
            if (this.type === "doc-start")
              doc.start.push(this.sourceToken);
            this.stack.push(doc);
            return;
          }
        }
        yield {
          type: "error",
          offset: this.offset,
          message: `Unexpected ${this.type} token in YAML stream`,
          source: this.source
        };
      }
      *document(doc) {
        if (doc.value)
          return yield* this.lineEnd(doc);
        switch (this.type) {
          case "doc-start": {
            if (findNonEmptyIndex(doc.start) !== -1) {
              yield* this.pop();
              yield* this.step();
            } else
              doc.start.push(this.sourceToken);
            return;
          }
          case "anchor":
          case "tag":
          case "space":
          case "comment":
          case "newline":
            doc.start.push(this.sourceToken);
            return;
        }
        const bv = this.startBlockValue(doc);
        if (bv)
          this.stack.push(bv);
        else {
          yield {
            type: "error",
            offset: this.offset,
            message: `Unexpected ${this.type} token in YAML document`,
            source: this.source
          };
        }
      }
      *scalar(scalar) {
        if (this.type === "map-value-ind") {
          const prev = getPrevProps(this.peek(2));
          const start = getFirstKeyStartProps(prev);
          let sep2;
          if (scalar.end) {
            sep2 = scalar.end;
            sep2.push(this.sourceToken);
            delete scalar.end;
          } else
            sep2 = [this.sourceToken];
          const map = {
            type: "block-map",
            offset: scalar.offset,
            indent: scalar.indent,
            items: [{ start, key: scalar, sep: sep2 }]
          };
          this.onKeyLine = true;
          this.stack[this.stack.length - 1] = map;
        } else
          yield* this.lineEnd(scalar);
      }
      *blockScalar(scalar) {
        switch (this.type) {
          case "space":
          case "comment":
          case "newline":
            scalar.props.push(this.sourceToken);
            return;
          case "scalar":
            scalar.source = this.source;
            this.atNewLine = true;
            this.indent = 0;
            if (this.onNewLine) {
              let nl = this.source.indexOf("\n") + 1;
              while (nl !== 0) {
                this.onNewLine(this.offset + nl);
                nl = this.source.indexOf("\n", nl) + 1;
              }
            }
            yield* this.pop();
            break;
          /* istanbul ignore next should not happen */
          default:
            yield* this.pop();
            yield* this.step();
        }
      }
      *blockMap(map) {
        const it = map.items[map.items.length - 1];
        switch (this.type) {
          case "newline":
            this.onKeyLine = false;
            if (it.value) {
              const end = "end" in it.value ? it.value.end : void 0;
              const last = Array.isArray(end) ? end[end.length - 1] : void 0;
              if (last?.type === "comment")
                end?.push(this.sourceToken);
              else
                map.items.push({ start: [this.sourceToken] });
            } else if (it.sep) {
              it.sep.push(this.sourceToken);
            } else {
              it.start.push(this.sourceToken);
            }
            return;
          case "space":
          case "comment":
            if (it.value) {
              map.items.push({ start: [this.sourceToken] });
            } else if (it.sep) {
              it.sep.push(this.sourceToken);
            } else {
              if (this.atIndentedComment(it.start, map.indent)) {
                const prev = map.items[map.items.length - 2];
                const end = prev?.value?.end;
                if (Array.isArray(end)) {
                  arrayPushArray(end, it.start);
                  end.push(this.sourceToken);
                  map.items.pop();
                  return;
                }
              }
              it.start.push(this.sourceToken);
            }
            return;
        }
        if (this.indent >= map.indent) {
          const atMapIndent = !this.onKeyLine && this.indent === map.indent;
          const atNextItem = atMapIndent && (it.sep || it.explicitKey) && this.type !== "seq-item-ind";
          let start = [];
          if (atNextItem && it.sep && !it.value) {
            const nl = [];
            for (let i = 0; i < it.sep.length; ++i) {
              const st = it.sep[i];
              switch (st.type) {
                case "newline":
                  nl.push(i);
                  break;
                case "space":
                  break;
                case "comment":
                  if (st.indent > map.indent)
                    nl.length = 0;
                  break;
                default:
                  nl.length = 0;
              }
            }
            if (nl.length >= 2)
              start = it.sep.splice(nl[1]);
          }
          switch (this.type) {
            case "anchor":
            case "tag":
              if (atNextItem || it.value) {
                start.push(this.sourceToken);
                map.items.push({ start });
                this.onKeyLine = true;
              } else if (it.sep) {
                it.sep.push(this.sourceToken);
              } else {
                it.start.push(this.sourceToken);
              }
              return;
            case "explicit-key-ind":
              if (!it.sep && !it.explicitKey) {
                it.start.push(this.sourceToken);
                it.explicitKey = true;
              } else if (atNextItem || it.value) {
                start.push(this.sourceToken);
                map.items.push({ start, explicitKey: true });
              } else {
                this.stack.push({
                  type: "block-map",
                  offset: this.offset,
                  indent: this.indent,
                  items: [{ start: [this.sourceToken], explicitKey: true }]
                });
              }
              this.onKeyLine = true;
              return;
            case "map-value-ind":
              if (it.explicitKey) {
                if (!it.sep) {
                  if (includesToken(it.start, "newline")) {
                    Object.assign(it, { key: null, sep: [this.sourceToken] });
                  } else {
                    const start2 = getFirstKeyStartProps(it.start);
                    this.stack.push({
                      type: "block-map",
                      offset: this.offset,
                      indent: this.indent,
                      items: [{ start: start2, key: null, sep: [this.sourceToken] }]
                    });
                  }
                } else if (it.value) {
                  map.items.push({ start: [], key: null, sep: [this.sourceToken] });
                } else if (includesToken(it.sep, "map-value-ind")) {
                  this.stack.push({
                    type: "block-map",
                    offset: this.offset,
                    indent: this.indent,
                    items: [{ start, key: null, sep: [this.sourceToken] }]
                  });
                } else if (isFlowToken(it.key) && !includesToken(it.sep, "newline")) {
                  const start2 = getFirstKeyStartProps(it.start);
                  const key = it.key;
                  const sep2 = it.sep;
                  sep2.push(this.sourceToken);
                  delete it.key;
                  delete it.sep;
                  this.stack.push({
                    type: "block-map",
                    offset: this.offset,
                    indent: this.indent,
                    items: [{ start: start2, key, sep: sep2 }]
                  });
                } else if (start.length > 0) {
                  it.sep = it.sep.concat(start, this.sourceToken);
                } else {
                  it.sep.push(this.sourceToken);
                }
              } else {
                if (!it.sep) {
                  Object.assign(it, { key: null, sep: [this.sourceToken] });
                } else if (it.value || atNextItem) {
                  map.items.push({ start, key: null, sep: [this.sourceToken] });
                } else if (includesToken(it.sep, "map-value-ind")) {
                  this.stack.push({
                    type: "block-map",
                    offset: this.offset,
                    indent: this.indent,
                    items: [{ start: [], key: null, sep: [this.sourceToken] }]
                  });
                } else {
                  it.sep.push(this.sourceToken);
                }
              }
              this.onKeyLine = true;
              return;
            case "alias":
            case "scalar":
            case "single-quoted-scalar":
            case "double-quoted-scalar": {
              const fs = this.flowScalar(this.type);
              if (atNextItem || it.value) {
                map.items.push({ start, key: fs, sep: [] });
                this.onKeyLine = true;
              } else if (it.sep) {
                this.stack.push(fs);
              } else {
                Object.assign(it, { key: fs, sep: [] });
                this.onKeyLine = true;
              }
              return;
            }
            default: {
              const bv = this.startBlockValue(map);
              if (bv) {
                if (bv.type === "block-seq") {
                  if (!it.explicitKey && it.sep && !includesToken(it.sep, "newline")) {
                    yield* this.pop({
                      type: "error",
                      offset: this.offset,
                      message: "Unexpected block-seq-ind on same line with key",
                      source: this.source
                    });
                    return;
                  }
                } else if (atMapIndent) {
                  map.items.push({ start });
                }
                this.stack.push(bv);
                return;
              }
            }
          }
        }
        yield* this.pop();
        yield* this.step();
      }
      *blockSequence(seq) {
        const it = seq.items[seq.items.length - 1];
        switch (this.type) {
          case "newline":
            if (it.value) {
              const end = "end" in it.value ? it.value.end : void 0;
              const last = Array.isArray(end) ? end[end.length - 1] : void 0;
              if (last?.type === "comment")
                end?.push(this.sourceToken);
              else
                seq.items.push({ start: [this.sourceToken] });
            } else
              it.start.push(this.sourceToken);
            return;
          case "space":
          case "comment":
            if (it.value)
              seq.items.push({ start: [this.sourceToken] });
            else {
              if (this.atIndentedComment(it.start, seq.indent)) {
                const prev = seq.items[seq.items.length - 2];
                const end = prev?.value?.end;
                if (Array.isArray(end)) {
                  arrayPushArray(end, it.start);
                  end.push(this.sourceToken);
                  seq.items.pop();
                  return;
                }
              }
              it.start.push(this.sourceToken);
            }
            return;
          case "anchor":
          case "tag":
            if (it.value || this.indent <= seq.indent)
              break;
            it.start.push(this.sourceToken);
            return;
          case "seq-item-ind":
            if (this.indent !== seq.indent)
              break;
            if (it.value || includesToken(it.start, "seq-item-ind"))
              seq.items.push({ start: [this.sourceToken] });
            else
              it.start.push(this.sourceToken);
            return;
        }
        if (this.indent > seq.indent) {
          const bv = this.startBlockValue(seq);
          if (bv) {
            this.stack.push(bv);
            return;
          }
        }
        yield* this.pop();
        yield* this.step();
      }
      *flowCollection(fc) {
        const it = fc.items[fc.items.length - 1];
        if (this.type === "flow-error-end") {
          let top;
          do {
            yield* this.pop();
            top = this.peek(1);
          } while (top?.type === "flow-collection");
        } else if (fc.end.length === 0) {
          switch (this.type) {
            case "comma":
            case "explicit-key-ind":
              if (!it || it.sep)
                fc.items.push({ start: [this.sourceToken] });
              else
                it.start.push(this.sourceToken);
              return;
            case "map-value-ind":
              if (!it || it.value)
                fc.items.push({ start: [], key: null, sep: [this.sourceToken] });
              else if (it.sep)
                it.sep.push(this.sourceToken);
              else
                Object.assign(it, { key: null, sep: [this.sourceToken] });
              return;
            case "space":
            case "comment":
            case "newline":
            case "anchor":
            case "tag":
              if (!it || it.value)
                fc.items.push({ start: [this.sourceToken] });
              else if (it.sep)
                it.sep.push(this.sourceToken);
              else
                it.start.push(this.sourceToken);
              return;
            case "alias":
            case "scalar":
            case "single-quoted-scalar":
            case "double-quoted-scalar": {
              const fs = this.flowScalar(this.type);
              if (!it || it.value)
                fc.items.push({ start: [], key: fs, sep: [] });
              else if (it.sep)
                this.stack.push(fs);
              else
                Object.assign(it, { key: fs, sep: [] });
              return;
            }
            case "flow-map-end":
            case "flow-seq-end":
              fc.end.push(this.sourceToken);
              return;
          }
          const bv = this.startBlockValue(fc);
          if (bv)
            this.stack.push(bv);
          else {
            yield* this.pop();
            yield* this.step();
          }
        } else {
          const parent = this.peek(2);
          if (parent.type === "block-map" && (this.type === "map-value-ind" && parent.indent === fc.indent || this.type === "newline" && !parent.items[parent.items.length - 1].sep)) {
            yield* this.pop();
            yield* this.step();
          } else if (this.type === "map-value-ind" && parent.type !== "flow-collection") {
            const prev = getPrevProps(parent);
            const start = getFirstKeyStartProps(prev);
            fixFlowSeqItems(fc);
            const sep2 = fc.end.splice(1, fc.end.length);
            sep2.push(this.sourceToken);
            const map = {
              type: "block-map",
              offset: fc.offset,
              indent: fc.indent,
              items: [{ start, key: fc, sep: sep2 }]
            };
            this.onKeyLine = true;
            this.stack[this.stack.length - 1] = map;
          } else {
            yield* this.lineEnd(fc);
          }
        }
      }
      flowScalar(type) {
        if (this.onNewLine) {
          let nl = this.source.indexOf("\n") + 1;
          while (nl !== 0) {
            this.onNewLine(this.offset + nl);
            nl = this.source.indexOf("\n", nl) + 1;
          }
        }
        return {
          type,
          offset: this.offset,
          indent: this.indent,
          source: this.source
        };
      }
      startBlockValue(parent) {
        switch (this.type) {
          case "alias":
          case "scalar":
          case "single-quoted-scalar":
          case "double-quoted-scalar":
            return this.flowScalar(this.type);
          case "block-scalar-header":
            return {
              type: "block-scalar",
              offset: this.offset,
              indent: this.indent,
              props: [this.sourceToken],
              source: ""
            };
          case "flow-map-start":
          case "flow-seq-start":
            return {
              type: "flow-collection",
              offset: this.offset,
              indent: this.indent,
              start: this.sourceToken,
              items: [],
              end: []
            };
          case "seq-item-ind":
            return {
              type: "block-seq",
              offset: this.offset,
              indent: this.indent,
              items: [{ start: [this.sourceToken] }]
            };
          case "explicit-key-ind": {
            this.onKeyLine = true;
            const prev = getPrevProps(parent);
            const start = getFirstKeyStartProps(prev);
            start.push(this.sourceToken);
            return {
              type: "block-map",
              offset: this.offset,
              indent: this.indent,
              items: [{ start, explicitKey: true }]
            };
          }
          case "map-value-ind": {
            this.onKeyLine = true;
            const prev = getPrevProps(parent);
            const start = getFirstKeyStartProps(prev);
            return {
              type: "block-map",
              offset: this.offset,
              indent: this.indent,
              items: [{ start, key: null, sep: [this.sourceToken] }]
            };
          }
        }
        return null;
      }
      atIndentedComment(start, indent) {
        if (this.type !== "comment")
          return false;
        if (this.indent <= indent)
          return false;
        return start.every((st) => st.type === "newline" || st.type === "space");
      }
      *documentEnd(docEnd) {
        if (this.type !== "doc-mode") {
          if (docEnd.end)
            docEnd.end.push(this.sourceToken);
          else
            docEnd.end = [this.sourceToken];
          if (this.type === "newline")
            yield* this.pop();
        }
      }
      *lineEnd(token) {
        switch (this.type) {
          case "comma":
          case "doc-start":
          case "doc-end":
          case "flow-seq-end":
          case "flow-map-end":
          case "map-value-ind":
            yield* this.pop();
            yield* this.step();
            break;
          case "newline":
            this.onKeyLine = false;
          // fallthrough
          case "space":
          case "comment":
          default:
            if (token.end)
              token.end.push(this.sourceToken);
            else
              token.end = [this.sourceToken];
            if (this.type === "newline")
              yield* this.pop();
        }
      }
    };
    exports.Parser = Parser;
  }
});

// node_modules/yaml/dist/public-api.js
var require_public_api = __commonJS({
  "node_modules/yaml/dist/public-api.js"(exports) {
    "use strict";
    var composer = require_composer();
    var Document = require_Document();
    var errors = require_errors();
    var log = require_log();
    var identity = require_identity();
    var lineCounter = require_line_counter();
    var parser = require_parser();
    function parseOptions(options) {
      const prettyErrors = options.prettyErrors !== false;
      const lineCounter$1 = options.lineCounter || prettyErrors && new lineCounter.LineCounter() || null;
      return { lineCounter: lineCounter$1, prettyErrors };
    }
    function parseAllDocuments(source, options = {}) {
      const { lineCounter: lineCounter2, prettyErrors } = parseOptions(options);
      const parser$1 = new parser.Parser(lineCounter2?.addNewLine);
      const composer$1 = new composer.Composer(options);
      const docs = Array.from(composer$1.compose(parser$1.parse(source)));
      if (prettyErrors && lineCounter2)
        for (const doc of docs) {
          doc.errors.forEach(errors.prettifyError(source, lineCounter2));
          doc.warnings.forEach(errors.prettifyError(source, lineCounter2));
        }
      if (docs.length > 0)
        return docs;
      return Object.assign([], { empty: true }, composer$1.streamInfo());
    }
    function parseDocument(source, options = {}) {
      const { lineCounter: lineCounter2, prettyErrors } = parseOptions(options);
      const parser$1 = new parser.Parser(lineCounter2?.addNewLine);
      const composer$1 = new composer.Composer(options);
      let doc = null;
      for (const _doc of composer$1.compose(parser$1.parse(source), true, source.length)) {
        if (!doc)
          doc = _doc;
        else if (doc.options.logLevel !== "silent") {
          doc.errors.push(new errors.YAMLParseError(_doc.range.slice(0, 2), "MULTIPLE_DOCS", "Source contains multiple documents; please use YAML.parseAllDocuments()"));
          break;
        }
      }
      if (prettyErrors && lineCounter2) {
        doc.errors.forEach(errors.prettifyError(source, lineCounter2));
        doc.warnings.forEach(errors.prettifyError(source, lineCounter2));
      }
      return doc;
    }
    function parse(src, reviver, options) {
      let _reviver = void 0;
      if (typeof reviver === "function") {
        _reviver = reviver;
      } else if (options === void 0 && reviver && typeof reviver === "object") {
        options = reviver;
      }
      const doc = parseDocument(src, options);
      if (!doc)
        return null;
      doc.warnings.forEach((warning) => log.warn(doc.options.logLevel, warning));
      if (doc.errors.length > 0) {
        if (doc.options.logLevel !== "silent")
          throw doc.errors[0];
        else
          doc.errors = [];
      }
      return doc.toJS(Object.assign({ reviver: _reviver }, options));
    }
    function stringify(value, replacer, options) {
      let _replacer = null;
      if (typeof replacer === "function" || Array.isArray(replacer)) {
        _replacer = replacer;
      } else if (options === void 0 && replacer) {
        options = replacer;
      }
      if (typeof options === "string")
        options = options.length;
      if (typeof options === "number") {
        const indent = Math.round(options);
        options = indent < 1 ? void 0 : indent > 8 ? { indent: 8 } : { indent };
      }
      if (value === void 0) {
        const { keepUndefined } = options ?? replacer ?? {};
        if (!keepUndefined)
          return void 0;
      }
      if (identity.isDocument(value) && !_replacer)
        return value.toString(options);
      return new Document.Document(value, _replacer, options).toString(options);
    }
    exports.parse = parse;
    exports.parseAllDocuments = parseAllDocuments;
    exports.parseDocument = parseDocument;
    exports.stringify = stringify;
  }
});

// node_modules/yaml/dist/index.js
var require_dist = __commonJS({
  "node_modules/yaml/dist/index.js"(exports) {
    "use strict";
    var composer = require_composer();
    var Document = require_Document();
    var Schema = require_Schema();
    var errors = require_errors();
    var Alias = require_Alias();
    var identity = require_identity();
    var Pair = require_Pair();
    var Scalar = require_Scalar();
    var YAMLMap = require_YAMLMap();
    var YAMLSeq = require_YAMLSeq();
    var cst = require_cst();
    var lexer = require_lexer();
    var lineCounter = require_line_counter();
    var parser = require_parser();
    var publicApi = require_public_api();
    var visit = require_visit();
    exports.Composer = composer.Composer;
    exports.Document = Document.Document;
    exports.Schema = Schema.Schema;
    exports.YAMLError = errors.YAMLError;
    exports.YAMLParseError = errors.YAMLParseError;
    exports.YAMLWarning = errors.YAMLWarning;
    exports.Alias = Alias.Alias;
    exports.isAlias = identity.isAlias;
    exports.isCollection = identity.isCollection;
    exports.isDocument = identity.isDocument;
    exports.isMap = identity.isMap;
    exports.isNode = identity.isNode;
    exports.isPair = identity.isPair;
    exports.isScalar = identity.isScalar;
    exports.isSeq = identity.isSeq;
    exports.Pair = Pair.Pair;
    exports.Scalar = Scalar.Scalar;
    exports.YAMLMap = YAMLMap.YAMLMap;
    exports.YAMLSeq = YAMLSeq.YAMLSeq;
    exports.CST = cst;
    exports.Lexer = lexer.Lexer;
    exports.LineCounter = lineCounter.LineCounter;
    exports.Parser = parser.Parser;
    exports.parse = publicApi.parse;
    exports.parseAllDocuments = publicApi.parseAllDocuments;
    exports.parseDocument = publicApi.parseDocument;
    exports.stringify = publicApi.stringify;
    exports.visit = visit.visit;
    exports.visitAsync = visit.visitAsync;
  }
});

// ../flare/src/main.ts
import { existsSync } from "node:fs";
import { appendFile, readFile as readFile4, writeFile as writeFile2 } from "node:fs/promises";
import { homedir as homedir2 } from "node:os";
import { join as join2, resolve as resolve2 } from "node:path";
import { parseArgs } from "node:util";

// ../flare/src/core/brand.ts
var SITE = "https://dawnfix.dev";
var BRAND = {
  suite: "Dawnfix",
  product: "Flare",
  fullName: "Dawnfix Flare",
  cli: "flare",
  org: "Dawnfix",
  homepage: `${SITE}/flare`,
  docsUrl: `${SITE}/flare#run`,
  checksUrl: `${SITE}/flare#checks`,
  userAgent: "dawnfix-flare/0.1 (read-only audit)",
  /**
   * The closing line of a scan (`--json` carries it as `pitch`): the free daily workflow in
   * the customer's own CI, and the one hosted extra. No prices: Enterprise is "Contact us".
   */
  pitch: {
    line: "Run this audit every day in your own GitHub Actions, free: templates/github/workflows/dawnfix-flare.yml in the Dawnfix repo. Your Cloudflare token stays a GitHub secret. An email the morning a new exposure appears is Dawnfix Enterprise.",
    url: `${SITE}/flare#daily`
  }
};
var CLOUDFLARE_API = "https://api.cloudflare.com/client/v4";

// ../flare/src/core/client.ts
var CfApiError = class extends Error {
  constructor(path, status, codes, message) {
    super(message);
    this.path = path;
    this.status = status;
    this.codes = codes;
  }
  path;
  status;
  codes;
  /** 403, or 401/400 with the "not authorized" family of codes: the token lacks a scope. */
  get isPermission() {
    return this.status === 403 || this.status === 401 || this.codes.includes(1e4) || this.codes.includes(9109);
  }
};
var CfClient = class {
  constructor(opts) {
    this.opts = opts;
  }
  opts;
  active = 0;
  queue = [];
  calls = [];
  async slot(fn) {
    const limit = this.opts.concurrency ?? 4;
    if (this.active >= limit) await new Promise((r) => this.queue.push(r));
    this.active++;
    try {
      return await fn();
    } finally {
      this.active--;
      this.queue.shift()?.();
    }
  }
  async get(path, query = {}) {
    return this.request("GET", path, query);
  }
  async request(method, path, query = {}) {
    if (method !== "GET") throw new Error(`${BRAND.cli} is read-only: refused ${method} ${path}`);
    const qs = new URLSearchParams(Object.entries(query).map(([k, v]) => [k, String(v)])).toString();
    const base = Object.hasOwn(this.opts, "baseUrl") && this.opts.baseUrl ? this.opts.baseUrl : CLOUDFLARE_API;
    const url = `${base}${path}${qs ? `?${qs}` : ""}`;
    const sleep = this.opts.sleep ?? ((ms) => new Promise((r) => setTimeout(r, ms)));
    return this.slot(async () => {
      for (let attempt2 = 0; ; attempt2++) {
        this.calls.push(`GET ${path}${qs ? `?${qs}` : ""}`);
        const res = await this.opts.fetch(url, {
          method: "GET",
          headers: { authorization: `Bearer ${this.opts.token}`, "user-agent": BRAND.userAgent, accept: "application/json" }
        });
        if ((res.status === 429 || res.status >= 500) && attempt2 < (this.opts.maxRetries ?? 3)) {
          const after = Number(res.headers.get("retry-after"));
          await sleep(Number.isFinite(after) && after > 0 ? Math.min(after, 60) * 1e3 : 500 * 2 ** attempt2);
          continue;
        }
        let body;
        try {
          body = await res.json();
        } catch {
          body = void 0;
        }
        if (res.status >= 400 || !body || body.success === false) {
          const errs = body?.errors ?? [];
          throw new CfApiError(
            path,
            res.status,
            errs.map((e) => e.code),
            errs.map((e) => `${e.code}: ${e.message}`).join("; ") || `HTTP ${res.status}`
          );
        }
        return body;
      }
    });
  }
  /** Follows result_info.total_pages. Endpoints without result_info return their one page. */
  async getAll(path, query = {}, perPage = 100) {
    const out = [];
    for (let page = 1; page <= 1e3; page++) {
      const env = await this.get(path, { ...query, page, per_page: perPage });
      const items = Array.isArray(env.result) ? env.result : [];
      out.push(...items);
      const total = env.result_info?.total_pages;
      if (!total || page >= total || items.length === 0) break;
    }
    return out;
  }
};

// ../flare/src/core/collect.ts
function describeError(e) {
  if (e instanceof CfApiError) return e.isPermission ? `token lacks the scope (HTTP ${e.status})` : `HTTP ${e.status}: ${e.message}`;
  return e instanceof Error ? e.message : String(e);
}
async function attempt(gaps, account, what, fn) {
  try {
    return await fn();
  } catch (e) {
    const r = describeError(e);
    const existing = gaps.find((g) => g.account === account && g.what === what);
    if (existing) {
      const m = /\((\d+) items\)$/.exec(existing.reason);
      const n = m ? Number(m[1]) + 1 : 2;
      existing.reason = `${existing.reason.replace(/ \(\d+ items\)$/, "")} (${n} items)`;
    } else gaps.push({ account, what, reason: r });
    return void 0;
  }
}
function mapBinding(b) {
  return {
    type: String(b.type ?? ""),
    name: String(b.name ?? ""),
    ...b.namespace_id !== void 0 ? { namespaceId: String(b.namespace_id) } : {},
    ...b.type === "service" && b.service ? { service: String(b.service) } : {}
  };
}
function mapToken(t, scope) {
  const policies = (Array.isArray(t.policies) ? t.policies : []).map((p) => {
    const groups = Array.isArray(p.permission_groups) ? p.permission_groups : [];
    const ids = groups.filter((g) => g.id !== void 0).map((g) => String(g.id));
    return {
      effect: p.effect === "deny" ? "deny" : "allow",
      // A group listed by id only keeps its id here until resolveGroupNames finds the name.
      permissionGroups: groups.map((g) => String(g.name ?? g.id ?? "")),
      ...ids.length ? { permissionGroupIds: ids } : {},
      resources: flattenResources(p.resources)
    };
  });
  const cond = t.condition?.request_ip;
  return {
    id: String(t.id),
    name: String(t.name ?? t.id),
    ...t.status ? { status: String(t.status) } : {},
    ...t.expires_on ? { expiresOn: String(t.expires_on) } : {},
    ...t.last_used_on ? { lastUsedOn: String(t.last_used_on) } : {},
    ...t.issued_on ? { issuedOn: String(t.issued_on) } : {},
    ipRestricted: Boolean(cond && ((cond.in?.length ?? 0) > 0 || (cond.not_in?.length ?? 0) > 0)),
    policies,
    scope
  };
}
function flattenResources(r) {
  if (!r || typeof r !== "object") return [];
  const out = [];
  for (const [k, v] of Object.entries(r)) {
    out.push(k);
    if (v && typeof v === "object") out.push(...flattenResources(v));
  }
  return out;
}
function unnamedGroupIds(tokens) {
  const out = /* @__PURE__ */ new Set();
  for (const t of tokens) for (const p of t.policies) for (const id of p.permissionGroupIds ?? []) if (p.permissionGroups.includes(id)) out.add(id);
  return [...out];
}
function resolveGroupNames(tokens, names) {
  for (const t of tokens) for (const p of t.policies) p.permissionGroups = p.permissionGroups.map((g) => names.get(g) ?? g);
}
function mapAccessApp(a) {
  const domains = /* @__PURE__ */ new Set();
  const workers = /* @__PURE__ */ new Set();
  let allWorkers = false;
  if (typeof a.domain === "string" && a.domain) domains.add(a.domain);
  for (const d of Array.isArray(a.self_hosted_domains) ? a.self_hosted_domains : []) if (typeof d === "string") domains.add(d);
  for (const d of Array.isArray(a.destinations) ? a.destinations : []) {
    if (d && d.type === "public" && typeof d.uri === "string") domains.add(d.uri);
    if (d && d.type === "worker") {
      const name = d.script_name ?? d.worker_name ?? d.script ?? d.name;
      if (typeof name === "string" && name) workers.add(name);
    }
    if (d && d.type === "all_workers") allWorkers = true;
  }
  return {
    id: a.id,
    name: a.name,
    type: a.type,
    domains: [...domains],
    ...workers.size ? { workers: [...workers] } : {},
    ...allWorkers ? { allWorkers } : {}
  };
}
async function collectToken(client, opts = {}) {
  let accounts;
  if (opts.accountIds?.length) {
    accounts = await Promise.all(
      opts.accountIds.map(async (id) => {
        try {
          const env = await client.get(`/accounts/${id}`);
          return { id, name: String(env.result?.name ?? id) };
        } catch {
          return { id, name: id };
        }
      })
    );
  } else {
    const raw = await client.getAll("/accounts", {}, 50);
    accounts = raw.map((a) => ({ id: String(a.id), name: String(a.name ?? a.id) }));
  }
  const snaps = await Promise.all(accounts.map((a) => collectAccount(client, a, opts)));
  const first = snaps[0];
  if (first) {
    const userTokens = await attempt(
      first.gaps,
      first.name,
      "user API tokens",
      async () => (await client.getAll("/user/tokens", {}, 50)).map((t) => mapToken(t, "user"))
    );
    if (userTokens) {
      const ids = unnamedGroupIds(userTokens);
      if (ids.length) {
        const list = await attempt(first.gaps, first.name, "permission group names (user)", () => client.get("/user/tokens/permission_groups"));
        if (list) resolveGroupNames(userTokens, new Map((list.result ?? []).map((g) => [String(g.id), String(g.name ?? g.id)])));
      }
      first.tokens = [...first.tokens ?? [], ...userTokens];
    }
  }
  return snaps;
}
async function collectAccount(client, acct, opts) {
  const gaps = [];
  const A = acct.name;
  const base = `/accounts/${acct.id}`;
  const snap = { id: acct.id, name: acct.name, gaps };
  const [sub, scriptsRaw, domainsRaw, zonesRaw, appsRaw, tokensRaw] = await Promise.all([
    attempt(gaps, A, "workers.dev subdomain", () => client.get(`${base}/workers/subdomain`)),
    attempt(gaps, A, "Workers scripts", () => client.get(`${base}/workers/scripts`)),
    attempt(gaps, A, "Workers custom domains", () => client.get(`${base}/workers/domains`)),
    attempt(gaps, A, "zones", () => client.getAll("/zones", { "account.id": acct.id }, 50)),
    attempt(gaps, A, "Access applications", () => client.getAll(`${base}/access/apps`, {}, 1e3)),
    attempt(gaps, A, "account API tokens", () => client.getAll(`${base}/tokens`, {}, 50))
  ]);
  if (sub?.result?.subdomain) snap.workersSubdomain = String(sub.result.subdomain);
  if (scriptsRaw) {
    snap.scripts = await Promise.all(
      (scriptsRaw.result ?? []).map(async (s) => {
        const name = String(s.id);
        const script = {
          name,
          ...s.created_on ? { createdOn: String(s.created_on) } : {},
          ...s.modified_on ? { modifiedOn: String(s.modified_on) } : {},
          ...s.compatibility_date ? { compatibilityDate: String(s.compatibility_date) } : {},
          handlers: Array.isArray(s.handlers) ? s.handlers.map(String) : [],
          routes: (Array.isArray(s.routes) ? s.routes : []).map((r) => String(r.pattern))
        };
        if (opts.shallow) return script;
        const enc = encodeURIComponent(name);
        const [sd, settings, secrets, deps, sched] = await Promise.all([
          attempt(gaps, A, "per-script workers.dev / preview flags", () => client.get(`${base}/workers/scripts/${enc}/subdomain`)),
          attempt(gaps, A, "per-script bindings", () => client.get(`${base}/workers/scripts/${enc}/settings`)),
          attempt(gaps, A, "per-script secret names", () => client.get(`${base}/workers/scripts/${enc}/secrets`)),
          attempt(gaps, A, "per-script deployments", () => client.get(`${base}/workers/scripts/${enc}/deployments`)),
          s.handlers?.includes?.("scheduled") ? attempt(gaps, A, "per-script cron schedules", () => client.get(`${base}/workers/scripts/${enc}/schedules`)) : Promise.resolve(void 0)
        ]);
        if (sched?.result) script.crons = (Array.isArray(sched.result.schedules) ? sched.result.schedules : []).map((x) => String(x.cron));
        if (sd?.result) script.subdomain = { enabled: Boolean(sd.result.enabled), previewsEnabled: Boolean(sd.result.previews_enabled) };
        if (settings?.result) {
          script.bindings = (Array.isArray(settings.result.bindings) ? settings.result.bindings : []).map(mapBinding);
          if (!script.compatibilityDate && settings.result.compatibility_date) script.compatibilityDate = String(settings.result.compatibility_date);
        }
        if (secrets?.result) script.secretNames = secrets.result.map((x) => String(x.name)).sort();
        const latest = deps?.result?.deployments?.[0];
        if (latest?.created_on) script.lastDeployedOn = String(latest.created_on);
        return script;
      })
    );
  }
  if (domainsRaw) {
    snap.customDomains = (domainsRaw.result ?? []).map(
      (d) => ({
        hostname: String(d.hostname),
        service: String(d.service),
        ...d.zone_id ? { zoneId: String(d.zone_id) } : {},
        ...d.zone_name ? { zoneName: String(d.zone_name) } : {}
      })
    );
  }
  if (zonesRaw) {
    snap.zones = await Promise.all(
      zonesRaw.map(async (z) => {
        const zid = String(z.id);
        const zone = { id: zid, name: String(z.name), ...z.status ? { status: String(z.status) } : {} };
        const zb = `/zones/${zid}`;
        const [routes, dns, tls, https, hsts] = await Promise.all([
          attempt(gaps, A, "zone Workers routes", () => client.get(`${zb}/workers/routes`)),
          attempt(gaps, A, "zone DNS records", () => client.getAll(`${zb}/dns_records`, {}, 1e3)),
          attempt(gaps, A, "zone setting min_tls_version", () => client.get(`${zb}/settings/min_tls_version`)),
          attempt(gaps, A, "zone setting always_use_https", () => client.get(`${zb}/settings/always_use_https`)),
          attempt(gaps, A, "zone setting security_header", () => client.get(`${zb}/settings/security_header`))
        ]);
        if (routes) zone.routes = (routes.result ?? []).map((r) => ({ id: String(r.id), pattern: String(r.pattern), ...r.script ? { script: String(r.script) } : {} }));
        if (dns) zone.dns = dns.map((r) => ({ id: String(r.id), type: String(r.type), name: String(r.name), content: String(r.content ?? ""), ...r.proxied !== void 0 ? { proxied: Boolean(r.proxied) } : {} }));
        const settings = {};
        if (tls?.result?.value !== void 0) settings.minTlsVersion = String(tls.result.value);
        if (https?.result?.value !== void 0) settings.alwaysUseHttps = String(https.result.value);
        const sts = hsts?.result?.value?.strict_transport_security;
        if (hsts?.result) settings.hsts = { enabled: Boolean(sts?.enabled), maxAge: Number(sts?.max_age ?? 0), includeSubdomains: Boolean(sts?.include_subdomains) };
        if (tls || https || hsts) zone.settings = settings;
        return zone;
      })
    );
  }
  if (appsRaw) snap.accessApps = appsRaw.map(mapAccessApp);
  if (tokensRaw) {
    snap.tokens = tokensRaw.map((t) => mapToken(t, "account"));
    if (unnamedGroupIds(snap.tokens).length) {
      const list = await attempt(gaps, A, "permission group names", () => client.get(`${base}/tokens/permission_groups`));
      if (list) resolveGroupNames(snap.tokens, new Map((list.result ?? []).map((g) => [String(g.id), String(g.name ?? g.id)])));
    }
  }
  return snap;
}

// ../flare/src/core/hosts.ts
function hostOf(pattern) {
  return pattern.replace(/^[a-z]+:\/\//i, "").split("/")[0].toLowerCase().replace(/\.$/, "");
}
function pathOf(pattern) {
  const p = pattern.replace(/^[a-z]+:\/\//i, "");
  const at = p.indexOf("/");
  return at < 0 ? "" : p.slice(at);
}
function hostMatches(rule, host) {
  const r = rule.toLowerCase();
  const h = host.toLowerCase();
  if (r === h || r === "*") return true;
  if (r.startsWith("*.")) return h.endsWith(r.slice(1)) && h.length > r.length - 1;
  if (r.startsWith("*")) return h.endsWith(r.slice(1));
  return false;
}
function accessCoverage(accessDomain, host) {
  if (!hostMatches(hostOf(accessDomain), host)) return "none";
  const path = pathOf(accessDomain);
  return path === "" || path === "/" || path === "/*" ? "full" : "partial";
}
function monthsBetween(from, to) {
  return (to.getUTCFullYear() - from.getUTCFullYear()) * 12 + (to.getUTCMonth() - from.getUTCMonth()) - (to.getUTCDate() < from.getUTCDate() ? 1 : 0);
}
function daysBetween(from, to) {
  return Math.floor((to.getTime() - from.getTime()) / 864e5);
}

// ../flare/src/core/checks/context.ts
function buildContext(snap, opts) {
  const matched = /* @__PURE__ */ new Set();
  const accounts = snap.accounts.map((a) => {
    const scriptNames = new Set((a.scripts ?? []).map((s) => s.name));
    const hostsByScript = /* @__PURE__ */ new Map();
    const add = (script, host) => {
      if (!hostsByScript.has(script)) hostsByScript.set(script, /* @__PURE__ */ new Set());
      hostsByScript.get(script).add(host);
    };
    for (const d of a.customDomains ?? []) add(d.service, d.hostname.toLowerCase());
    for (const z of a.zones ?? []) for (const r of z.routes ?? []) if (r.script) add(r.script, hostOf(r.pattern));
    for (const s of a.scripts ?? []) for (const p of s.routes) add(s.name, hostOf(p));
    const local = /* @__PURE__ */ new Map();
    for (const w of snap.local) {
      if (scriptNames.has(w.name)) {
        local.set(w.name, w);
        matched.add(w);
      }
    }
    return { snap: a, scriptNames, hostsByScript, local };
  });
  return { snap, opts, accounts, unmatchedLocal: snap.local.filter((w) => !matched.has(w)) };
}
var label = (a) => a.name || a.id;

// ../flare/src/core/checks/exposure.ts
var WD_FIX = 'Set "workers_dev": false in the wrangler config and redeploy (or Worker > Settings > Domains & Routes > workers.dev > Disable).';
var PV_FIX = 'Set "preview_urls": false in the wrangler config and redeploy (or Worker > Settings > Domains & Routes > Preview URLs > Disable).';
var servesHttp = (handlers) => handlers.length === 0 || handlers.includes("fetch");
function cronOnly(w) {
  if (!w.entry) return false;
  return (w.entry.scheduled || (w.crons?.length ?? 0) > 0) && !w.entry.fetch && !w.entry.opaqueDefault;
}
function effectiveWorkersDev(w) {
  if (w.workersDev !== void 0) return { value: w.workersDev, explicit: true };
  return { value: w.routes.length === 0, explicit: false };
}
function accessOnWorkersDev(apps, script, host) {
  return (apps ?? []).some(
    (app) => app.allWorkers === true || (app.workers ?? []).includes(script) || host !== void 0 && app.domains.some((d) => accessCoverage(d, host) === "full")
  );
}
function checkWorkersDev(ctx) {
  const out = [];
  const reported = /* @__PURE__ */ new Set();
  for (const a of ctx.accounts) {
    for (const s of a.snap.scripts ?? []) {
      const lw = a.local.get(s.name);
      const hosts = a.hostsByScript.get(s.name);
      const sub = a.snap.workersSubdomain;
      const url = sub ? `${s.name}.${sub}.workers.dev` : `${s.name}.<subdomain>.workers.dev`;
      const ACCESS = " An Access application covers it, so a visitor must sign in first.";
      if (s.subdomain?.enabled) {
        reported.add(s.name);
        const hasHosts = (hosts?.size ?? 0) > 0;
        const guarded = accessOnWorkersDev(a.snap.accessApps, s.name, sub ? url : void 0);
        out.push({
          check: "workers-dev-enabled",
          severity: !servesHttp(s.handlers) || guarded ? "low" : hasHosts ? "high" : "medium",
          account: label(a.snap),
          resource: s.name,
          title: (hasHosts ? "Reachable on workers.dev, around its custom domain" : "Public on workers.dev") + (guarded ? " (behind Access)" : ""),
          detail: (hasHosts ? `${url} serves the same Worker as ${[...hosts].join(", ")}, but outside that zone's WAF, rate-limiting rules${guarded ? "" : " and Access"}.` : `${url} is this Worker's only public address; no zone rules apply to it.`) + (guarded ? ACCESS : ""),
          fix: hasHosts ? WD_FIX : `Give it a custom domain, then: ${WD_FIX}`,
          source: lw && !effectiveWorkersDev(lw).explicit ? "api+local" : "api"
        });
      }
      if (s.subdomain?.previewsEnabled) {
        reported.add(`preview:${s.name}`);
        const guarded = accessOnWorkersDev(a.snap.accessApps, s.name, sub ? `00000000-${url}` : void 0);
        out.push({
          check: "preview-urls-enabled",
          severity: servesHttp(s.handlers) && !guarded ? "medium" : "low",
          account: label(a.snap),
          resource: s.name,
          title: "Preview URLs enabled" + (guarded ? " (behind Access)" : ""),
          detail: `Every uploaded version gets its own public <version>-${url} address, with no zone rules in front.` + (guarded ? ACCESS : ""),
          fix: PV_FIX,
          source: lw && lw.previewUrls === void 0 ? "api+local" : "api"
        });
      }
    }
  }
  for (const w of ctx.snap.local) {
    const wd = effectiveWorkersDev(w);
    if (!reported.has(w.name)) {
      if (wd.value) {
        const cron = cronOnly(w);
        out.push({
          check: "workers-dev-enabled",
          severity: cron ? "low" : "medium",
          account: "local",
          resource: w.name,
          title: wd.explicit ? "workers_dev is true in config" : "workers_dev not set and no routes, so it defaults to on",
          detail: `${w.file}${w.env ? ` [env.${w.env}]` : ""}: the next deploy publishes this Worker on workers.dev.` + (cron ? " The source shows a scheduled handler and no fetch handler, so the address would only answer with an error." : ""),
          fix: WD_FIX,
          source: "local"
        });
      } else if (!wd.explicit) {
        out.push({
          check: "workers-dev-enabled",
          severity: "info",
          account: "local",
          resource: w.name,
          title: "workers_dev not set explicitly",
          detail: `${w.file}${w.env ? ` [env.${w.env}]` : ""}: off today only because routes exist; removing the routes turns workers.dev on.`,
          fix: 'Add "workers_dev": false.',
          source: "local"
        });
      }
    }
    if (!reported.has(`preview:${w.name}`)) {
      if (w.previewUrls === true || w.previewUrls === void 0 && wd.value) {
        out.push({
          check: "preview-urls-enabled",
          severity: w.previewUrls === true ? "medium" : "low",
          account: "local",
          resource: w.name,
          title: w.previewUrls === true ? "preview_urls is true in config" : "preview_urls not set; it follows workers_dev, which is on",
          detail: `${w.file}${w.env ? ` [env.${w.env}]` : ""}`,
          fix: PV_FIX,
          source: "local"
        });
      } else if (w.previewUrls === void 0) {
        out.push({
          check: "preview-urls-enabled",
          severity: "info",
          account: "local",
          resource: w.name,
          title: "preview_urls not set explicitly",
          detail: `${w.file}${w.env ? ` [env.${w.env}]` : ""}: wrangler leaves an existing setting unchanged when the key is absent.`,
          fix: 'Add "preview_urls": false.',
          source: "local"
        });
      }
    }
  }
  return out;
}
function isPublicByPolicy(ctx, host) {
  return ctx.opts.publicHostnames.some((rule) => hostMatches(rule, host));
}
function checkHostnameAuth(ctx) {
  const out = [];
  for (const a of ctx.accounts) {
    const apps = a.snap.accessApps;
    for (const [script, hosts] of a.hostsByScript) {
      if (!a.scriptNames.has(script)) continue;
      const lw = a.local.get(script);
      const appAuth = ctx.opts.appAuthScripts.includes(script) || (lw?.authMarkers.length ?? 0) > 0;
      for (const host of hosts) {
        if (isPublicByPolicy(ctx, host) || appAuth) continue;
        const coverage = apps?.map((app) => app.domains.map((d) => accessCoverage(d, host))).flat() ?? [];
        if (coverage.includes("full")) continue;
        const partial = coverage.includes("partial");
        out.push({
          check: "hostname-without-auth",
          severity: apps === void 0 ? "low" : partial ? "low" : "medium",
          account: label(a.snap),
          resource: host,
          title: partial ? "Access covers only some paths" : "No Access application and no app sign-in found",
          detail: `Served by ${script}. ` + (apps === void 0 ? "Access applications could not be read, so this is unverified. " : partial ? "An Access app matches this host on a sub-path only. " : "No Access application matches this hostname. ") + (lw ? "The repo shows no sign-in marker." : "No local repo was scanned for this Worker, so app-level sign-in is unknown."),
          fix: `If it is meant to be public, add "${host}" to publicHostnames. Otherwise put a self-hosted Access application on it, or list the script in appAuthScripts if it signs users in itself.`,
          source: lw ? "api+local" : "api"
        });
      }
    }
  }
  for (const w of ctx.unmatchedLocal) {
    if (w.authMarkers.length > 0 || ctx.opts.appAuthScripts.includes(w.name)) continue;
    for (const r of w.routes) {
      const host = r.pattern.split("/")[0].toLowerCase();
      if (isPublicByPolicy(ctx, host)) continue;
      out.push({
        check: "hostname-without-auth",
        severity: "info",
        account: "local",
        resource: host,
        title: "No sign-in marker in the repo (Access not checked)",
        detail: `${w.file}: route for ${w.name}; no API data matched this Worker, so Access was not checked.`,
        fix: `Add "${host}" to publicHostnames if public; otherwise check it has an Access application.`,
        source: "local"
      });
    }
  }
  return out;
}

// ../flare/src/core/checks/lifecycle.ts
var NON_HTTP_ENTRY = ["queue", "email", "tail", "alarm"];
function checkDeadScripts(ctx) {
  const out = [];
  for (const a of ctx.accounts) {
    const scripts = a.snap.scripts ?? [];
    const complete = a.snap.zones !== void 0 && a.snap.customDomains !== void 0 && (a.snap.zones ?? []).every((z) => z.routes !== void 0);
    const bound = new Set(scripts.flatMap((s) => (s.bindings ?? []).filter((b) => b.type === "service" && b.service).map((b) => b.service)));
    for (const s of scripts) {
      const reasons = [];
      const hosts = a.hostsByScript.get(s.name)?.size ?? 0;
      const hasCron = (s.crons?.length ?? 0) > 0 || s.crons === void 0 && s.handlers.includes("scheduled");
      const otherEntry = s.handlers.some((h) => NON_HTTP_ENTRY.includes(h));
      const reachable = hosts > 0 || s.subdomain?.enabled === true || hasCron || otherEntry || bound.has(s.name);
      if (complete && s.subdomain !== void 0 && !reachable) {
        reasons.push("no route, no custom domain, workers.dev off, no cron or queue/email handler, and no service binding points at it");
      }
      const last = s.lastDeployedOn ?? s.modifiedOn;
      const age = last ? daysBetween(new Date(last), ctx.opts.now) : void 0;
      if (age !== void 0 && age > ctx.opts.staleDays) reasons.push(`last deployed ${age} days ago (${last.slice(0, 10)})`);
      if (reasons.length === 0) continue;
      const unreachable = reasons.length === 2 || reasons[0].startsWith("no route");
      out.push({
        check: "dead-script",
        severity: reasons.length === 2 ? "medium" : "low",
        account: label(a.snap),
        resource: s.name,
        title: reasons.length === 2 ? "Unreachable and not deployed for a long time" : unreachable ? "Unreachable script" : `Not deployed for ${age} days`,
        detail: `${reasons.join("; ")}. Old scripts keep their secrets and bindings live.`,
        fix: unreachable ? `If nothing uses it: wrangler delete --name ${s.name}. Otherwise note why it is kept.` : "Redeploy to pick up runtime fixes, or delete it if retired.",
        source: "api"
      });
    }
  }
  return out;
}
function checkCompatDates(ctx) {
  const out = [];
  const limit = ctx.opts.compatMonths;
  const seen = /* @__PURE__ */ new Set();
  const make = (account, resource, date, where, source) => {
    const d = /* @__PURE__ */ new Date(`${date}T00:00:00Z`);
    if (Number.isNaN(d.getTime())) return void 0;
    const months = monthsBetween(d, ctx.opts.now);
    if (months < limit) return void 0;
    return {
      check: "compat-date-old",
      severity: months >= limit * 2 ? "medium" : "low",
      account,
      resource,
      title: `compatibility_date is ${months} months old`,
      detail: `${date}${where}. Runtime behaviour fixes after that date are off for this Worker.`,
      fix: "Read the compatibility flags changelog for the dates in between, raise compatibility_date, run the tests, redeploy.",
      source
    };
  };
  for (const a of ctx.accounts) {
    for (const s of a.snap.scripts ?? []) {
      if (!s.compatibilityDate) continue;
      const lw = a.local.get(s.name);
      const f = make(label(a.snap), s.name, s.compatibilityDate, lw ? ` (deployed; ${lw.file} has ${lw.compatibilityDate ?? "none"})` : " (deployed)", lw ? "api+local" : "api");
      if (f) out.push(f);
      seen.add(s.name);
    }
  }
  for (const w of ctx.snap.local) {
    if (seen.has(w.name) || !w.compatibilityDate) continue;
    const f = make("local", w.name, w.compatibilityDate, ` in ${w.file}`, "local");
    if (f) out.push(f);
  }
  return out;
}
function checkSecrets(ctx) {
  const findings = [];
  const baseline = {};
  const prev = ctx.opts.secretsBaseline;
  for (const a of ctx.accounts) {
    for (const s of a.snap.scripts ?? []) {
      if (!s.secretNames) continue;
      const key = `${a.snap.id}/${s.name}`;
      baseline[key] = [...s.secretNames];
      const before = prev?.[key];
      if (!before) continue;
      const added = s.secretNames.filter((n) => !before.includes(n));
      const removed = before.filter((n) => !s.secretNames.includes(n));
      if (added.length === 0 && removed.length === 0) continue;
      findings.push({
        check: "secrets-changed",
        severity: removed.length ? "medium" : "low",
        account: label(a.snap),
        resource: s.name,
        title: `Secrets changed: ${s.secretNames.length} now, ${before.length} before`,
        detail: [added.length ? `added ${added.join(", ")}` : "", removed.length ? `removed ${removed.join(", ")}` : ""].filter(Boolean).join("; ") + ". Names only; values are never read.",
        fix: "Confirm the change was yours (wrangler secret list). A removed secret often breaks the next request that needs it.",
        source: "api"
      });
    }
  }
  for (const [k, v] of Object.entries(prev ?? {})) if (!(k in baseline)) baseline[k] = v;
  return { findings, baseline };
}

// ../flare/src/core/checks/ratelimit.ts
function nextFreeBlock(ids) {
  const nums = ids.map(Number).filter((n) => Number.isInteger(n) && n >= 0);
  if (nums.length === 0) return void 0;
  return String((Math.floor(Math.max(...nums) / 100) + 1) * 100 + 1);
}
function findingsFor(pool, account) {
  const out = [];
  const free = nextFreeBlock([...pool.keys()]);
  for (const [id, uses] of [...pool].sort(([a], [b]) => a.localeCompare(b, "en", { numeric: true }))) {
    const unique = /* @__PURE__ */ new Map();
    for (const u of uses) {
      const k = `${u.worker}\0${u.binding}`;
      const prev = unique.get(k);
      unique.set(k, prev && prev.from !== u.from ? { ...prev, from: "api", file: prev.file ?? u.file } : prev ?? u);
    }
    const list = [...unique.values()];
    const workers = [...new Set(list.map((u) => u.worker))].sort();
    const sources = new Set(uses.map((u) => u.from));
    const source = sources.size === 2 ? "api+local" : sources.has("api") ? "api" : "local";
    const where = list.map((u) => `${u.worker}.${u.binding}${u.file ? ` (${u.file})` : ""}`).join(", ");
    if (workers.length > 1) {
      out.push({
        check: "ratelimit-namespace-shared",
        severity: "high",
        account,
        resource: `namespace ${id}`,
        title: `Rate-limit namespace ${id} shared by ${workers.length} Workers`,
        detail: `${where}. They share counters, so traffic to one spends the others' limit.`,
        fix: `Give each Worker its own ids${free ? ` (next free block: ${free}-${Number(free) + 98})` : ""} and redeploy each.`,
        source
      });
    } else if (list.length > 1) {
      out.push({
        check: "ratelimit-namespace-shared",
        severity: "medium",
        account,
        resource: `namespace ${id}`,
        title: `Two limits in ${workers[0]} share namespace ${id}`,
        detail: `${where}. Both bindings count against the same counters, so neither limit holds as written.`,
        fix: `Give each binding its own namespace_id${free ? ` (next free block: ${free})` : ""}.`,
        source
      });
    }
  }
  return out;
}
function checkRatelimitNamespaces(ctx) {
  const out = [];
  const add = (pool, id, u) => {
    if (!pool.has(id)) pool.set(id, []);
    pool.get(id).push(u);
  };
  const single = ctx.accounts.length === 1;
  for (const a of ctx.accounts) {
    const pool = /* @__PURE__ */ new Map();
    for (const s of a.snap.scripts ?? []) {
      for (const b of s.bindings ?? []) if (b.type === "ratelimit" && b.namespaceId) add(pool, b.namespaceId, { worker: s.name, binding: b.name, from: "api" });
    }
    const locals = [...a.local.values(), ...single ? ctx.unmatchedLocal : []];
    for (const w of locals) for (const r of w.ratelimitNamespaces) add(pool, r.namespaceId, { worker: w.name, binding: r.binding, from: "local", file: w.file });
    out.push(...findingsFor(pool, label(a.snap)));
  }
  if (!single) {
    const pool = /* @__PURE__ */ new Map();
    for (const w of ctx.unmatchedLocal) for (const r of w.ratelimitNamespaces) add(pool, r.namespaceId, { worker: w.name, binding: r.binding, from: "local", file: w.file });
    out.push(...findingsFor(pool, "local"));
  }
  return out;
}

// ../flare/src/core/checks/routing.ts
function checkRoutesToMissingScripts(ctx) {
  const out = [];
  for (const a of ctx.accounts) {
    if (!a.snap.scripts) continue;
    for (const z of a.snap.zones ?? []) {
      for (const r of z.routes ?? []) {
        if (r.script && !a.scriptNames.has(r.script)) {
          out.push({
            check: "route-to-missing-script",
            severity: "high",
            account: label(a.snap),
            resource: r.pattern,
            title: `Route points at deleted Worker "${r.script}"`,
            detail: `Zone ${z.name}, route id ${r.id}. Requests here get an error, and a new script with that name would take the route over.`,
            fix: `Delete the route (zone ${z.name} > Workers Routes), or redeploy "${r.script}" if it should exist.`,
            source: "api"
          });
        }
      }
    }
    for (const d of a.snap.customDomains ?? []) {
      if (!a.scriptNames.has(d.service)) {
        out.push({
          check: "route-to-missing-script",
          severity: "high",
          account: label(a.snap),
          resource: d.hostname,
          title: `Custom domain bound to missing Worker "${d.service}"`,
          detail: `Zone ${d.zoneName ?? d.zoneId ?? "?"}.`,
          fix: `Detach the custom domain, or redeploy "${d.service}".`,
          source: "api"
        });
      }
    }
  }
  return out;
}
var PLACEHOLDER_A = /^192\.0\.2\.\d+$/;
var PLACEHOLDER_AAAA = /^100::(0)?$/i;
function checkDanglingDns(ctx) {
  const out = [];
  for (const a of ctx.accounts) {
    const zones = a.snap.zones ?? [];
    const routeHosts = zones.flatMap((z) => (z.routes ?? []).filter((r) => r.script).map((r) => hostOf(r.pattern)));
    const customHosts = new Set((a.snap.customDomains ?? []).map((d) => d.hostname.toLowerCase()));
    const namesByZone = new Map(zones.filter((z) => z.dns).map((z) => [z.name.toLowerCase(), new Set(z.dns.map((r) => r.name.toLowerCase()))]));
    const scripts = new Map((a.snap.scripts ?? []).map((s) => [s.name, s]));
    for (const z of zones) {
      for (const rec of z.dns ?? []) {
        const name = rec.name.toLowerCase();
        const target = rec.content.toLowerCase().replace(/\.$/, "");
        if (rec.type === "CNAME" && target.endsWith(".workers.dev") && a.snap.scripts) {
          const [script, sub] = target.split(".");
          const s = script ? scripts.get(script) : void 0;
          const otherSub = a.snap.workersSubdomain && sub !== a.snap.workersSubdomain.toLowerCase();
          if (otherSub || !s || s.subdomain?.enabled === false) {
            out.push({
              check: "dangling-dns",
              severity: otherSub ? "medium" : "high",
              account: label(a.snap),
              resource: name,
              title: otherSub ? "CNAME into a different workers.dev subdomain" : !s ? `CNAME to workers.dev for missing Worker "${script}"` : `CNAME to "${script}" on workers.dev, which is disabled`,
              detail: `${z.name}: ${name} CNAME ${target}.${otherSub ? ` This account's subdomain is ${a.snap.workersSubdomain}; the target belongs to another account or a renamed subdomain.` : ""}`,
              fix: "Delete the record, or replace it with a Workers custom domain on the script it should serve.",
              source: "api"
            });
          }
          continue;
        }
        if (rec.type === "CNAME") {
          const zoneOfTarget = [...namesByZone.keys()].find((zn) => target === zn || target.endsWith(`.${zn}`));
          if (zoneOfTarget && !namesByZone.get(zoneOfTarget).has(target) && !customHosts.has(target)) {
            const wildcard = [...namesByZone.get(zoneOfTarget)].some((n) => n.startsWith("*.") && hostMatches(n, target));
            if (!wildcard) {
              out.push({
                check: "dangling-dns",
                severity: "medium",
                account: label(a.snap),
                resource: name,
                title: "CNAME to a name that no longer exists",
                detail: `${z.name}: ${name} CNAME ${target}, and zone ${zoneOfTarget} has no record for ${target}.`,
                fix: "Delete the record, or recreate its target.",
                source: "api"
              });
            }
          }
          continue;
        }
        const placeholder = rec.type === "A" && PLACEHOLDER_A.test(target) || rec.type === "AAAA" && PLACEHOLDER_AAAA.test(target);
        if (placeholder && a.snap.zones?.every((zz) => zz.routes !== void 0)) {
          const served = routeHosts.some((h) => hostMatches(h, name)) || customHosts.has(name);
          if (!served) {
            out.push({
              check: "dangling-dns",
              severity: "medium",
              account: label(a.snap),
              resource: name,
              title: "Placeholder record with no Workers route",
              detail: `${z.name}: ${name} ${rec.type} ${rec.content}${rec.proxied ? " (proxied)" : ""}. That address only exists to carry a Workers route, and no route matches it any more.`,
              fix: "Delete the record, or add the route back.",
              source: "api"
            });
          }
        }
      }
    }
  }
  return out;
}

// ../flare/src/core/checks/tokens.ts
var WRITE = /\b(write|edit|admin)\b/i;
var ALL_RESOURCES = /^com\.cloudflare\.api\.(account|user)\.\*$|^com\.cloudflare\.api\.account\.zone\.\*$/;
var BROAD_WRITE_GROUPS = 8;
var UNUSED_DAYS = 90;
function tokenIssues(t, now) {
  const out = [];
  if (t.status && t.status !== "active") return out;
  const resource = `${t.name} (${t.scope} token)`;
  const writes = t.policies.filter((p) => p.effect === "allow").flatMap((p) => p.permissionGroups.filter((g) => WRITE.test(g)).map((g) => ({ g, p })));
  const everywhere = writes.filter(({ p }) => p.resources.some((r) => ALL_RESOURCES.test(r)));
  const uniqueWrites = [...new Set(writes.map((w) => w.g))];
  if (everywhere.length > 0) {
    const groups = [...new Set(everywhere.map((w) => w.g))];
    out.push({
      check: "token-over-scoped",
      severity: "high",
      resource,
      title: "Write access on all accounts or all zones",
      detail: `${groups.slice(0, 6).join(", ")}${groups.length > 6 ? ` and ${groups.length - 6} more` : ""} on every ${everywhere.some(({ p }) => p.resources.some((r) => r.includes("zone"))) ? "zone" : "account"}.${t.ipRestricted ? "" : " No client IP restriction."}`,
      fix: "Roll a replacement scoped to the one account and the zones it needs, then delete this one."
    });
  } else if (uniqueWrites.length >= BROAD_WRITE_GROUPS) {
    out.push({
      check: "token-over-scoped",
      severity: "medium",
      resource,
      title: `${uniqueWrites.length} write permission groups`,
      detail: `${uniqueWrites.slice(0, 6).join(", ")}, ... A token this broad is usually several jobs sharing one secret.`,
      fix: "Split it into one token per job, each with only what that job writes."
    });
  }
  if (!t.expiresOn) {
    out.push({
      check: "token-no-expiry",
      severity: writes.length ? "medium" : "low",
      resource,
      title: "Never expires",
      detail: `Issued ${t.issuedOn?.slice(0, 10) ?? "on an unknown date"}${writes.length ? ", with write access" : ""}.`,
      fix: "Set an expiry (Edit token > TTL) and a reminder to roll it."
    });
  }
  const lastUsed = t.lastUsedOn ? daysBetween(new Date(t.lastUsedOn), now) : void 0;
  if (lastUsed !== void 0 && lastUsed > UNUSED_DAYS) {
    out.push({
      check: "token-unused",
      severity: "low",
      resource,
      title: `Unused for ${lastUsed} days`,
      detail: `Last used ${t.lastUsedOn.slice(0, 10)}.`,
      fix: "Delete it if nothing needs it."
    });
  }
  return out;
}
function checkTokens(ctx) {
  const seen = /* @__PURE__ */ new Set();
  const out = [];
  for (const a of ctx.accounts) {
    for (const t of a.snap.tokens ?? []) {
      if (seen.has(t.id)) continue;
      seen.add(t.id);
      for (const f of tokenIssues(t, ctx.opts.now)) out.push({ ...f, account: t.scope === "user" ? "user" : label(a.snap), source: "api" });
    }
  }
  return out;
}

// ../flare/src/core/checks/zones.ts
var HSTS_MIN_AGE = 15552e3;
function checkZoneTls(ctx) {
  const out = [];
  for (const a of ctx.accounts) {
    for (const z of a.snap.zones ?? []) {
      if (z.status && z.status !== "active") continue;
      const s = z.settings;
      if (!s) continue;
      const push = (severity, title, detail, fix) => out.push({ check: "zone-tls", severity, account: label(a.snap), resource: z.name, title, detail, fix, source: "api" });
      if (s.minTlsVersion && Number(s.minTlsVersion) < 1.2) {
        push("medium", `Minimum TLS ${s.minTlsVersion}`, "TLS 1.0 and 1.1 are deprecated and fail PCI DSS.", "SSL/TLS > Edge Certificates > Minimum TLS Version: 1.2.");
      }
      if (s.alwaysUseHttps === "off") {
        push("medium", "Always Use HTTPS is off", "Plain-HTTP requests are served instead of redirected.", "SSL/TLS > Edge Certificates > Always Use HTTPS: on.");
      }
      if (s.hsts && !s.hsts.enabled) {
        push("low", "HSTS off", "Browsers will try plain HTTP first on every new visit.", "SSL/TLS > Edge Certificates > HTTP Strict Transport Security: enable, max-age 6 months or more, once every subdomain serves HTTPS.");
      } else if (s.hsts && s.hsts.maxAge < HSTS_MIN_AGE) {
        push("low", `HSTS max-age ${s.hsts.maxAge}s`, "Below 6 months, so it lapses for visitors who come back rarely.", "Raise max-age to 15552000 or more.");
      }
    }
  }
  return out;
}

// ../flare/src/core/types.ts
var SEVERITIES = ["critical", "high", "medium", "low", "info"];
var severityRank = (s) => SEVERITIES.length - SEVERITIES.indexOf(s);
var CHECK_IDS = [
  "workers-dev-enabled",
  "preview-urls-enabled",
  "hostname-without-auth",
  "ratelimit-namespace-shared",
  "route-to-missing-script",
  "dangling-dns",
  "dead-script",
  "compat-date-old",
  "secrets-changed",
  "token-over-scoped",
  "token-no-expiry",
  "token-unused",
  "zone-tls"
];
var DEFAULT_OPTIONS = {
  publicHostnames: [],
  appAuthScripts: [],
  staleDays: 180,
  compatMonths: 12
};

// ../flare/src/core/audit.ts
function audit(snap, opts) {
  const ctx = buildContext(snap, opts);
  const secrets = checkSecrets(ctx);
  const findings = [
    ...checkWorkersDev(ctx),
    ...checkHostnameAuth(ctx),
    ...checkRatelimitNamespaces(ctx),
    ...checkRoutesToMissingScripts(ctx),
    ...checkDanglingDns(ctx),
    ...checkDeadScripts(ctx),
    ...checkCompatDates(ctx),
    ...secrets.findings,
    ...checkTokens(ctx),
    ...checkZoneTls(ctx)
  ].sort((a, b) => severityRank(b.severity) - severityRank(a.severity) || a.check.localeCompare(b.check) || a.account.localeCompare(b.account) || a.resource.localeCompare(b.resource));
  const summary = Object.fromEntries(SEVERITIES.map((s) => [s, 0]));
  for (const f of findings) summary[f.severity]++;
  return {
    result: {
      generatedAt: opts.now.toISOString(),
      findings,
      gaps: [...snap.accounts.flatMap((a) => a.gaps), ...snap.localGaps],
      summary,
      accounts: snap.accounts.map((a) => ({ id: a.id, name: a.name, scripts: a.scripts?.length ?? 0, zones: a.zones?.length ?? 0 })),
      localFiles: new Set(snap.local.map((w) => w.file)).size
    },
    secretsBaseline: secrets.baseline
  };
}
async function collectSnapshot(input) {
  const accounts = [];
  const calls = [];
  const localGaps = [];
  for (const [i, token] of input.tokens.entries()) {
    const client = new CfClient({ token, fetch: input.fetch, ...input.concurrency ? { concurrency: input.concurrency } : {} });
    try {
      for (const a of await collectToken(client, input.collect)) if (!accounts.some((x) => x.id === a.id)) accounts.push(a);
    } catch (e) {
      localGaps.push({ account: `token #${i + 1}`, what: "account list", reason: describeError(e) });
    }
    calls.push(...client.calls);
  }
  return { snapshot: { takenAt: input.now.toISOString(), accounts, local: input.local ?? [], localGaps }, calls };
}
function failsAt(result, threshold) {
  if (threshold === "never") return false;
  return result.findings.some((f) => severityRank(f.severity) >= severityRank(threshold));
}

// ../flare/src/core/ingest.ts
var INGEST_SCHEMA = "dawnfix.flare/1";
var MAX_INGEST_ACCOUNTS = 100;
var ACCOUNT_SALT = "dawnfix.flare/1:account:";
var zero = () => Object.fromEntries(SEVERITIES.map((s) => [s, 0]));
async function hashAccountId(id) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(ACCOUNT_SALT + id));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}
async function ingestDoc(result) {
  if (result.accounts.length > MAX_INGEST_ACCOUNTS) {
    throw new Error(`${result.accounts.length} accounts in one run; the ingest takes at most ${MAX_INGEST_ACCOUNTS}`);
  }
  const findings = Object.fromEntries(CHECK_IDS.map((c) => [c, zero()]));
  const summary = zero();
  for (const f of result.findings) {
    findings[f.check][f.severity]++;
    summary[f.severity]++;
  }
  const ids = [...new Set(await Promise.all(result.accounts.map((a) => hashAccountId(a.id))))].sort();
  return {
    schema: INGEST_SCHEMA,
    generated_at: `${result.generatedAt.slice(0, 19)}Z`,
    accounts: ids.length,
    account_ids: ids,
    local_files: result.localFiles,
    gaps: result.gaps.length,
    summary,
    findings
  };
}

// ../flare/src/core/report/doc-style.ts
var DOC_STYLE = `
/* the document style (green Tech-Azur), one sheet for docs pages and reports */
:root{--doc-bg:#0e1013;--doc-card:#121418;--doc-text:#e6e8eb;--doc-soft:#b9bec6;--doc-accent:#7ad69a;--doc-rule:#2a2e35;--doc-border:#353a42;
--doc-th:#13261a;--doc-code:#1b1e23;--doc-pre:#14161a;--doc-tint:#10201a;
--doc-good-bg:#0f2a28;--doc-good:#5fd0c3;--doc-good-line:#1f5650;--doc-crit:#f28b82;--doc-weak:#f3b267}
@media (prefers-color-scheme:light),print{:root{--doc-bg:#ffffff;--doc-card:#ffffff;--doc-text:#1d1d1f;--doc-soft:#4a4f57;--doc-accent:#1a5e33;--doc-rule:#e1e4e8;--doc-border:#d5dae1;
--doc-th:#eaf4ec;--doc-code:#f1f3f6;--doc-pre:#f6f8fa;--doc-tint:#eaf4ec;
--doc-good-bg:#dff3f1;--doc-good:#0a5f57;--doc-good-line:#93d1c9;--doc-crit:#b3261e;--doc-weak:#a35200}}
body.doc-page{margin:0;background:var(--doc-bg);color:var(--doc-text);-webkit-text-size-adjust:100%;overflow-wrap:break-word}
body.doc-page *{box-sizing:border-box}
body.doc-page>main{max-width:960px;margin:0 auto;padding:32px 16px 56px}
article.doc{counter-reset:doc-h2;font-family:"DejaVu Sans",Verdana,"Segoe UI",system-ui,sans-serif;font-size:15px;line-height:1.55;color:var(--doc-text);-webkit-font-smoothing:auto;min-width:0}
article.doc h1{font-family:inherit;font-size:clamp(24px,3.4vw,30px);font-weight:700;letter-spacing:0;line-height:1.25;margin:0 0 14px;padding:0 0 8px;border-bottom:3px solid var(--doc-accent);color:var(--doc-text);background:none;max-width:none}
article.doc .page-head{align-items:flex-end}
article.doc .page-head h1{flex:1;margin-bottom:0}
article.doc .page-head+p,article.doc .page-head+.works{margin-top:14px}
article.doc .lead{font-size:16px;color:var(--doc-text);margin:0 0 24px;max-width:76ch}
article.doc .muted,article.doc .meta{color:var(--doc-soft)}
article.doc .eyebrow{font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--doc-accent);margin:0 0 6px}
article.doc h2{counter-increment:doc-h2;font-family:inherit;font-size:20px;font-weight:700;letter-spacing:0;line-height:1.3;color:var(--doc-accent);margin:36px 0 12px;padding-top:0;border-top:0;display:flex;gap:6px 10px;align-items:center;flex-wrap:wrap}
article.doc h2::before{content:counter(doc-h2) ".";font-variant-numeric:tabular-nums}
article.doc h2 svg.px{width:24px;height:24px}
article.doc h3,article.doc h4{font-family:inherit;font-size:15.5px;font-weight:700;letter-spacing:0;margin:22px 0 8px;color:var(--doc-text)}
article.doc p,article.doc li{color:var(--doc-text)}
article.doc p{margin:0 0 10px;max-width:80ch}
article.doc p.works{margin:12px 0 18px;font-size:14px}
article.doc a{color:var(--doc-accent);text-decoration:underline;text-decoration-color:color-mix(in srgb,var(--doc-accent) 40%,transparent);text-underline-offset:3px}
article.doc a:hover{text-decoration-color:currentColor}
article.doc hr{border:0;border-top:1px solid var(--doc-rule);margin:20px 0}
article.doc blockquote{margin:0 0 10px;padding:2px 12px;border-left:3px solid var(--doc-border);color:var(--doc-soft)}
article.doc mark{background:#fff1a8;color:#1d1d1f;padding:0 2px}

/* bullets: a small diamond, a hollow circle when nested */
article.doc ul:not(.checks):not(.plain){list-style:none;padding-left:22px;margin:0 0 10px}
article.doc ul:not(.checks):not(.plain)>li,article.doc ul.checks>li{position:relative}
article.doc ul.checks{gap:6px;margin:0 0 12px}
article.doc ul.checks li{padding-left:22px}
article.doc ul:not(.checks):not(.plain)>li::before,article.doc ul.checks>li::before{content:"\\25C6";position:absolute;left:4px;top:.42em;width:auto;height:auto;background:none;box-shadow:none;font-size:9px;line-height:1;color:var(--doc-text)}
article.doc ul:not(.checks):not(.plain)>li::before{left:-17px}
article.doc ul ul>li::before,article.doc ul.checks ul>li::before{content:"\\25E6";font-size:13px;top:.22em}
article.doc ul.plain{list-style:none;padding:0;margin:0 0 10px}
article.doc ol:not(.steps):not(.plain){padding-left:22px;margin:0 0 10px}
article.doc li{margin:2px 0}

/* numbered steps: a green numeral in a square, a thin rule between */
article.doc ol.steps>li{padding:0 0 22px 44px}
article.doc ol.steps>li::before{width:28px;height:28px;top:-1px;border-radius:3px;background:var(--doc-th);border:1px solid color-mix(in srgb,var(--doc-accent) 45%,transparent);color:var(--doc-accent);font:700 13px/1 "DejaVu Sans Mono",Menlo,Consolas,ui-monospace,monospace}
article.doc ol.steps>li::after{left:14px;top:32px;background:var(--doc-border)}
article.doc ol.steps>li>strong:first-child{font-weight:700;margin-bottom:6px}

/* code: grey, thin border, scrolls inside its box */
article.doc code,article.doc .mono{font-family:"DejaVu Sans Mono",Menlo,Consolas,ui-monospace,monospace;font-size:.85em;color:var(--doc-text)}
article.doc code{background:var(--doc-code);border:0;border-radius:3px;padding:1px 4px;overflow-wrap:anywhere}
article.doc figure.code,article.doc figure.snip{margin:0 0 14px;border:1px solid var(--doc-border);border-radius:3px;background:var(--doc-pre)}
article.doc figure.code figcaption,article.doc figure.snip figcaption{background:var(--doc-th);border-bottom:1px solid var(--doc-border);color:var(--doc-text);font-size:13px;font-weight:700;padding:6px 12px}
article.doc pre{font-family:"DejaVu Sans Mono",Menlo,Consolas,ui-monospace,monospace;background:var(--doc-pre);border:1px solid var(--doc-border);border-radius:3px;padding:12px 14px;margin:0 0 14px;font-size:13px;line-height:1.45;color:var(--doc-text);overflow-x:auto;max-width:100%}
article.doc pre.wrap-lines{white-space:pre-wrap;overflow-wrap:anywhere}
article.doc figure pre{border:0;border-radius:0;margin:0}
article.doc pre code{background:none;padding:0;font-size:inherit;border-radius:0;overflow-wrap:normal}
article.doc details:not(.docs-nav){margin:0 0 14px;border:1px solid var(--doc-border);border-radius:3px;padding:8px 12px;background:var(--doc-card)}
article.doc details:not(.docs-nav)>summary{cursor:pointer;font-weight:700}
article.doc details:not(.docs-nav)[open]>summary{margin-bottom:8px}
article.doc details pre{margin-bottom:4px}

/* tables: in a wrapper that scrolls on a phone, never the page */
article.doc .table-wrap,article.doc .wrap{overflow-x:auto;margin:6px 0 14px;max-width:100%}
article.doc table{width:100%;border-collapse:collapse;font-size:13.5px;margin:0}
article.doc th,article.doc td{border:1px solid var(--doc-border);padding:6px 8px;text-align:left;vertical-align:top;color:var(--doc-text);background:none}
article.doc th{background:var(--doc-th);font-weight:700;font-size:13px}
article.doc th.n,article.doc td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}

/* key figures: thin-bordered boxes in a row, two to a line on a phone */
article.doc .facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:0;margin:6px 0 18px;border:1px solid var(--doc-border);border-radius:3px;overflow:hidden}
article.doc .facts>div{padding:10px 12px;border-right:1px solid var(--doc-border);border-bottom:1px solid var(--doc-border);margin:-1px -1px 0 0;background:var(--doc-card)}
article.doc .facts>div:first-child,article.doc .facts>div.lead-fact{background:var(--doc-tint)}
article.doc .facts b{display:block;font-size:21px;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.25}
article.doc .facts span{display:block;font-size:12.5px;color:var(--doc-soft)}
article.doc .facts .good b{color:var(--doc-good)}
article.doc .facts .crit b,article.doc .crit-text{color:var(--doc-crit)}
article.doc .facts .weak b,article.doc .weak-text{color:var(--doc-weak)}

/* the site's cards (stat tiles) inside a document: square, thin, the doc's border */
article.doc .card{border-radius:3px;border:1px solid var(--doc-border);background:var(--doc-card);box-shadow:none}
article.doc .card b{font-weight:700}

/* items: one bordered block each (a finding, a saving), the label column tinted */
article.doc .items{list-style:none;padding:0;margin:0 0 12px;display:grid;gap:8px}
article.doc .items>li{margin:0;padding:10px 14px;border:1px solid var(--doc-border);border-left:4px solid var(--doc-accent);border-radius:3px;background:var(--doc-card);min-width:0}
article.doc .items>li::before{content:none}
article.doc .items>li.crit{border-left-color:#c62828}
article.doc .items>li.weak{border-left-color:#e07a00}
article.doc .items>li.mixed{border-left-color:#c9a400}
article.doc .items>li.unknown{border-left-color:#8a8f98}
article.doc .items .head{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline}
article.doc .items .head b{font-weight:700}
article.doc .items .head .end{margin-left:auto}
article.doc .items pre{margin:8px 0 2px;white-space:pre-wrap;overflow-wrap:anywhere}
article.doc .items p{margin:4px 0 0}

/* highlights: status pills, priority tags, callouts */
article.doc .pill,article.doc .pri{display:inline-block;font-family:inherit;font-weight:700;font-size:11.5px;line-height:1.35;padding:1px 7px;border-radius:9px;white-space:nowrap;letter-spacing:0;border:1px solid var(--doc-border);background:var(--doc-code);color:var(--doc-soft);text-transform:none}
article.doc .pill.crit{background:#fde2e1;color:#b3261e;border-color:#f1a7a3}
article.doc .pill.weak{background:#fff0db;color:#a35200;border-color:#f3c48a}
article.doc .pill.mixed{background:#fff8cc;color:#7a6300;border-color:#e8d777}
article.doc .pill.good{background:var(--doc-good-bg);color:var(--doc-good);border-color:var(--doc-good-line)}
article.doc .pill.unknown{background:#eceef1;color:#555b65;border-color:#c7ccd3}
article.doc .pill.accent{background:var(--doc-tint);color:var(--doc-accent);border-color:color-mix(in srgb,var(--doc-accent) 45%,transparent)}
article.doc .pri{border-radius:3px;border:0;color:#fff;padding:1px 5px}
article.doc .pri.p0{background:#c62828}
article.doc .pri.p1{background:#b86400}
article.doc .pri.p2{background:#6b7079}
article.doc .callout{display:block;margin:6px 0 14px;padding:10px 14px 2px;border:0;border-left:4px solid var(--doc-border);border-radius:3px;background:var(--doc-code);color:var(--doc-text)}
article.doc .callout.red{background:color-mix(in srgb,#c62828 10%,transparent);border-left-color:#c62828}
article.doc .callout.amber{background:color-mix(in srgb,#e07a00 10%,transparent);border-left-color:#e07a00}
article.doc .callout.accent{background:var(--doc-tint);border-left-color:var(--doc-accent)}
article.doc .callout.green{background:var(--doc-good-bg);border-left-color:var(--doc-good)}
article.doc .callout p{margin-bottom:8px}
article.doc p.callout{max-width:none;padding-bottom:10px}
article.doc footer{margin-top:36px;padding-top:12px;border-top:1px solid var(--doc-rule);font-size:13px;color:var(--doc-soft)}
article.doc footer p{margin:0 0 6px}

/* the site's buttons and pager inside a document: squarer, in the document's face */
article.doc .actions{margin:14px 0 0}
article.doc .btn,article.doc .button{font-family:inherit;border-radius:3px}
article.doc .pager a{border-radius:3px}
@media (max-width:600px){article.doc{font-size:15px}article.doc h2{font-size:18.5px;margin-top:30px}article.doc pre{font-size:12.5px}article.doc .facts{grid-template-columns:1fr 1fr}body.doc-page>main{padding:20px 16px 40px}}
@media print{body.doc-page>main{max-width:none;padding:0}article.doc .wrap,article.doc .table-wrap,article.doc pre{overflow:visible;white-space:pre-wrap}}
`;

// ../flare/src/core/report/html.ts
var esc = (s) => String(s).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
var CHECK_NAMES = {
  "workers-dev-enabled": "workers.dev exposure",
  "preview-urls-enabled": "Preview URLs",
  "hostname-without-auth": "Hostname without auth",
  "ratelimit-namespace-shared": "Rate-limit namespace clash",
  "route-to-missing-script": "Route to missing Worker",
  "dangling-dns": "Dangling DNS",
  "dead-script": "Dead script",
  "compat-date-old": "Old compatibility date",
  "secrets-changed": "Secrets changed",
  "token-over-scoped": "Over-scoped token",
  "token-no-expiry": "Token never expires",
  "token-unused": "Unused token",
  "zone-tls": "Zone TLS / HSTS"
};
var SEVERITY_PILL = {
  critical: "pri p0",
  high: "pill crit",
  medium: "pill weak",
  low: "pill mixed",
  info: "pill unknown"
};
var REPORT_CSS = `
article.doc .chips{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 20px}
article.doc .chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--doc-border);background:var(--doc-card);color:var(--doc-text);border-radius:3px;padding:5px 10px;font:inherit;font-size:14px;cursor:pointer}
article.doc .chip[aria-pressed="false"]{opacity:.45}
article.doc .chip b{font-variant-numeric:tabular-nums}
article.doc .items>li.f[data-sev=critical],article.doc .items>li.f[data-sev=high]{border-left-color:#c62828}
article.doc .items>li.f[data-sev=medium]{border-left-color:#e07a00}
article.doc .items>li.f[data-sev=low]{border-left-color:#c9a400}
article.doc .items>li.f[data-sev=info]{border-left-color:#8a8f98}
article.doc .f .chk{font-weight:700}
article.doc .f .acct{color:var(--doc-soft);font-size:13px}
article.doc .f .res{display:block;margin-top:6px;overflow-wrap:anywhere}
article.doc .f .title{font-weight:700;margin-top:2px}
article.doc .f .detail{color:var(--doc-soft);overflow-wrap:anywhere}
article.doc .f .fix{overflow-wrap:anywhere}
article.doc .f .fix b{color:var(--doc-accent);margin-right:4px}
@media (max-width:560px){article.doc .items .head .end{margin-left:0;width:100%}}
`;
function renderHtml(r) {
  const counts = SEVERITIES.map((s) => [s, r.summary[s]]);
  const rows = r.findings.map(
    (f) => `<li class="f" data-sev="${f.severity}">
  <div class="head"><span class="${SEVERITY_PILL[f.severity]}">${esc(f.severity)}</span><span class="chk">${esc(CHECK_NAMES[f.check] ?? f.check)}</span><span class="end acct">${esc(f.account)} · ${esc(f.source)}</span></div>
  <code class="res">${esc(f.resource)}</code>
  <div class="title">${esc(f.title)}</div>
  <p class="detail">${esc(f.detail)}</p>
  <p class="fix"><b>Fix</b> ${esc(f.fix)}</p>
</li>`
  ).join("\n");
  const gaps = r.gaps.length ? `<h2>Not checked</h2><p class="muted">These parts could not be read with the token given, so their checks did not run.</p><ul class="gaps">${r.gaps.map((g) => `<li><b>${esc(g.account)}</b> ${esc(g.what)} <span class="muted">— ${esc(g.reason)}</span></li>`).join("")}</ul>` : "";
  const accounts = r.accounts.map((a) => `<tr><td>${esc(a.name)}</td><td class="n">${esc(a.scripts)}</td><td class="n">${esc(a.zones)}</td></tr>`).join("");
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>${esc(BRAND.product)} audit</title>
<style>${DOC_STYLE}${REPORT_CSS}</style>
</head>
<body class="doc-page">
<main>
<article class="doc">
<p class="eyebrow">${esc(BRAND.fullName)}</p>
<h1>Cloudflare account and Workers audit</h1>
<p class="meta">${esc(r.generatedAt.slice(0, 16).replace("T", " "))} UTC · ${esc(r.accounts.length)} account(s) · ${esc(r.localFiles)} local wrangler file(s) · read-only</p>
<h2>Findings</h2>
<div class="chips" role="group" aria-label="Filter by severity">
${counts.map(([s, n]) => `<button class="chip" type="button" aria-pressed="true" data-filter="${s}"><span class="${SEVERITY_PILL[s]}">${s}</span> <b>${n}</b></button>`).join("\n")}
</div>
${r.findings.length ? `<ul class="items plain" id="findings">${rows}</ul>` : '<p class="callout green">No findings.</p>'}
${gaps}
<h2>Accounts</h2>
<div class="wrap"><table><thead><tr><th>Account</th><th class="n">Scripts</th><th class="n">Zones</th></tr></thead><tbody>${accounts || '<tr><td colspan="3" class="muted">None (local files only)</td></tr>'}</tbody></table></div>
<footer>${esc(BRAND.fullName)} · ${esc(BRAND.org)} · Generated with read-only API calls; secret values are never read.</footer>
</article>
</main>
<script>
document.querySelectorAll('.chip').forEach(function(b){b.addEventListener('click',function(){
var on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',String(on));
document.querySelectorAll('.f[data-sev="'+b.dataset.filter+'"]').forEach(function(li){li.hidden=!on;});});});
</script>
</body>
</html>
`;
}

// ../flare/src/core/report/markdown.ts
var MAX_SUMMARY_ROWS = 300;
var mdCell = (s) => String(s).replace(/[\r\n]+/g, " ").replace(/\\/g, "\\\\").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/`/g, "'").replace(/([*_[\]|])/g, "\\$1");
function renderMarkdown(r) {
  const counts = SEVERITIES.filter((s) => r.summary[s] > 0).map((s) => `${r.summary[s]} ${s}`);
  const lines = [
    `## ${BRAND.fullName}: Cloudflare audit`,
    "",
    `${r.generatedAt.slice(0, 16).replace("T", " ")} UTC · ${r.accounts.length} account(s) · ${r.localFiles} wrangler file(s) · read-only. **${counts.length ? counts.join(", ") : "no findings"}**.`,
    ""
  ];
  if (r.findings.length) {
    lines.push("| Severity | Check | Account | Resource | Finding | Fix |", "|---|---|---|---|---|---|");
    for (const f of r.findings.slice(0, MAX_SUMMARY_ROWS)) {
      lines.push(`| ${f.severity} | ${mdCell(CHECK_NAMES[f.check] ?? f.check)} | ${mdCell(f.account)} | ${mdCell(f.resource)} | ${mdCell(f.title)} | ${mdCell(f.fix)} |`);
    }
    if (r.findings.length > MAX_SUMMARY_ROWS) lines.push("", `${r.findings.length - MAX_SUMMARY_ROWS} more not shown; run the CLI with --html for all of them.`);
    lines.push("");
  }
  if (r.gaps.length) {
    lines.push(`<details><summary>Not checked (${r.gaps.length})</summary>`, "", ...r.gaps.map((g) => `- ${mdCell(g.account)}: ${mdCell(g.what)} (${mdCell(g.reason)})`), "", "</details>", "");
  }
  return lines.join("\n") + "\n";
}

// ../flare/src/core/report/text.ts
var COLORS = { critical: "\x1B[1;37;41m", high: "\x1B[31m", medium: "\x1B[33m", low: "\x1B[36m", info: "\x1B[2m" };
var RESET = "\x1B[0m";
var DIM = "\x1B[2m";
function cut(s, w) {
  return s.length <= w ? s.padEnd(w) : `${s.slice(0, w - 1)}…`;
}
function renderText(r, opts = {}) {
  const color = opts.color ?? false;
  const width = Math.max(80, opts.width ?? 120);
  const c = (code, s) => color ? `${code}${s}${RESET}` : s;
  const lines = [];
  const acc = r.accounts.map((a) => `${a.name} (${a.scripts} scripts, ${a.zones} zones)`).join(", ") || "none";
  lines.push(`${BRAND.fullName} — ${r.generatedAt.slice(0, 16).replace("T", " ")} UTC`);
  lines.push(`Accounts: ${acc}. Local wrangler files: ${r.localFiles}.`);
  lines.push("");
  const findings = r.findings;
  if (findings.length === 0) lines.push("No findings.");
  else {
    const wSev = 8, wCheck = 26, wAcct = 14;
    const rest = width - wSev - wCheck - wAcct - 8;
    const wRes = Math.max(18, Math.floor(rest * 0.38));
    const wTitle = rest - wRes;
    lines.push(c(DIM, [cut("SEVERITY", wSev), cut("CHECK", wCheck), cut("ACCOUNT", wAcct), cut("RESOURCE", wRes), "FINDING"].join("  ")));
    for (const f of findings) {
      lines.push([c(COLORS[f.severity], cut(f.severity.toUpperCase(), wSev)), cut(f.check, wCheck), cut(f.account, wAcct), cut(f.resource, wRes), cut(f.title, wTitle).trimEnd()].join("  "));
      lines.push(c(DIM, `${" ".repeat(wSev + 2)}fix: ${f.fix}`));
    }
  }
  lines.push("");
  lines.push(
    "Summary: " + Object.entries(r.summary).filter(([, n]) => n > 0).map(([s, n]) => c(COLORS[s], `${n} ${s}`)).join(", ") || "Summary: clean"
  );
  if (r.gaps.length) {
    lines.push("");
    lines.push(`Not checked (${r.gaps.length}):`);
    for (const g of r.gaps) lines.push(`  ${g.account}: ${g.what} — ${g.reason}`);
  }
  return lines.join("\n") + "\n";
}

// ../flare/src/node/config.ts
import { readFile } from "node:fs/promises";
var KEYS = /* @__PURE__ */ new Set(["publicHostnames", "appAuthScripts", "staleDays", "compatMonths", "accounts", "tokenEnv", "repos", "authMarkers", "failOn", "$schema", "//"]);
function validateConfig(raw, file) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error(`${file}: expected a JSON object`);
  const o = raw;
  if ("token" in o || "apiToken" in o) throw new Error(`${file}: put tokens in environment variables and list their names in tokenEnv`);
  for (const k of Object.keys(o)) if (!KEYS.has(k)) throw new Error(`${file}: unknown key "${k}"`);
  const strs = (k) => {
    if (o[k] !== void 0 && (!Array.isArray(o[k]) || !o[k].every((x) => typeof x === "string"))) throw new Error(`${file}: ${k} must be an array of strings`);
  };
  ["publicHostnames", "appAuthScripts", "accounts", "tokenEnv", "repos"].forEach(strs);
  for (const k of ["staleDays", "compatMonths"]) if (o[k] !== void 0 && (typeof o[k] !== "number" || o[k] <= 0)) throw new Error(`${file}: ${k} must be a positive number`);
  if (o.authMarkers !== void 0) {
    const m = o.authMarkers;
    if (!Array.isArray(m) || !m.every((x) => x && typeof x.label === "string" && typeof x.pattern === "string")) throw new Error(`${file}: authMarkers must be [{ "label", "pattern" }]`);
    for (const x of m) new RegExp(x.pattern, "i");
  }
  return o;
}
async function loadConfig(file, required) {
  if (!file) return {};
  let text;
  try {
    text = await readFile(file, "utf8");
  } catch {
    if (required) throw new Error(`config file not found: ${file}`);
    return {};
  }
  return validateConfig(JSON.parse(text), file);
}

// ../flare/src/node/scan.ts
import { readdir, readFile as readFile2, stat } from "node:fs/promises";
import { homedir } from "node:os";
import { basename, dirname, join, relative, resolve } from "node:path";

// ../flare/src/core/wrangler.ts
function parseJsonc(text) {
  let out = "";
  let i = 0;
  while (i < text.length) {
    const c = text[i];
    if (c === '"') {
      const start = i++;
      while (i < text.length && text[i] !== '"') i += text[i] === "\\" ? 2 : 1;
      out += text.slice(start, ++i);
    } else if (c === "/" && text[i + 1] === "/") {
      while (i < text.length && text[i] !== "\n") i++;
    } else if (c === "/" && text[i + 1] === "*") {
      i = text.indexOf("*/", i + 2);
      i = i < 0 ? text.length : i + 2;
    } else {
      out += c;
      i++;
    }
  }
  return JSON.parse(out.replace(/,(\s*[}\]])/g, "$1"));
}
var FORBIDDEN_KEYS = /* @__PURE__ */ new Set(["__proto__", "constructor", "prototype"]);
var table = () => /* @__PURE__ */ Object.create(null);
function parseToml(text) {
  const root = table();
  let current = root;
  let i = 0;
  const n = text.length;
  const ws = () => {
    while (i < n && (text[i] === " " || text[i] === "	")) i++;
  };
  const wsNl = () => {
    for (; ; ) {
      while (i < n && /\s/.test(text[i])) i++;
      if (text[i] === "#") while (i < n && text[i] !== "\n") i++;
      else break;
    }
  };
  const fail2 = (msg) => {
    const line = text.slice(0, i).split("\n").length;
    throw new Error(`TOML line ${line}: ${msg}`);
  };
  const parseString = () => {
    const q2 = text[i];
    const triple = text.startsWith(q2.repeat(3), i);
    if (triple) {
      i += 3;
      if (text[i] === "\n") i++;
      const end = text.indexOf(q2.repeat(3), i);
      if (end < 0) fail2("unterminated multi-line string");
      const s2 = text.slice(i, end);
      i = end + 3;
      return q2 === '"' ? unescape(s2) : s2;
    }
    i++;
    let s = "";
    while (i < n && text[i] !== q2) {
      if (text[i] === "\n") fail2("newline in string");
      if (q2 === '"' && text[i] === "\\") {
        s += text.slice(i, i + 2);
        i += 2;
      } else s += text[i++];
    }
    if (text[i] !== q2) fail2("unterminated string");
    i++;
    return q2 === '"' ? unescape(s) : s;
  };
  const unescape = (s) => s.replace(/\\(u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)/g, (_, e) => {
    if (e[0] === "u" || e[0] === "U") return String.fromCodePoint(parseInt(e.slice(1), 16));
    return { n: "\n", t: "	", r: "\r", '"': '"', "\\": "\\", b: "\b", f: "\f" }[e] ?? e;
  });
  const parseKey = () => {
    const parts = [];
    for (; ; ) {
      ws();
      if (text[i] === '"' || text[i] === "'") parts.push(parseString());
      else {
        const m = /^[A-Za-z0-9_-]+/.exec(text.slice(i));
        if (!m) fail2("expected a key");
        parts.push(m[0]);
        i += m[0].length;
      }
      if (FORBIDDEN_KEYS.has(parts[parts.length - 1])) fail2(`forbidden key "${parts[parts.length - 1]}"`);
      ws();
      if (text[i] === ".") i++;
      else return parts;
    }
  };
  const parseValue = () => {
    ws();
    const c = text[i];
    if (c === '"' || c === "'") return parseString();
    if (c === "[") {
      i++;
      const arr = [];
      for (; ; ) {
        wsNl();
        if (text[i] === "]") {
          i++;
          return arr;
        }
        arr.push(parseValue());
        wsNl();
        if (text[i] === ",") i++;
        else if (text[i] !== "]") fail2("expected , or ] in array");
      }
    }
    if (c === "{") {
      i++;
      const obj = table();
      ws();
      if (text[i] === "}") {
        i++;
        return obj;
      }
      for (; ; ) {
        const key = parseKey();
        if (text[i] !== "=") fail2("expected = in inline table");
        i++;
        setPath(obj, key, parseValue());
        ws();
        if (text[i] === ",") i++;
        else if (text[i] === "}") {
          i++;
          return obj;
        } else fail2("expected , or } in inline table");
      }
    }
    const m = /^[^\s,\]}#]+/.exec(text.slice(i));
    if (!m) fail2("expected a value");
    const raw = m[0];
    i += raw.length;
    if (raw === "true") return true;
    if (raw === "false") return false;
    if (/^[+-]?(\d[\d_]*)(\.\d+)?([eE][+-]?\d+)?$/.test(raw)) return Number(raw.replace(/_/g, ""));
    return raw;
  };
  const descend = (o, k) => {
    if (!Object.hasOwn(o, k)) o[k] = table();
    const next = Array.isArray(o[k]) ? o[k][o[k].length - 1] : o[k];
    if (next === null || typeof next !== "object") fail2(`key "${k}" is not a table`);
    return next;
  };
  const setPath = (obj, path, value) => {
    let o = obj;
    for (const k of path.slice(0, -1)) o = descend(o, k);
    o[path[path.length - 1]] = value;
  };
  const tableAt = (path, arrayTable) => {
    let o = root;
    path.forEach((k, idx) => {
      const last = idx === path.length - 1;
      if (last && arrayTable) {
        if (!Object.hasOwn(o, k) || !Array.isArray(o[k])) o[k] = [];
        const t = table();
        o[k].push(t);
        o = t;
        return;
      }
      o = descend(o, k);
    });
    return o;
  };
  for (; ; ) {
    wsNl();
    if (i >= n) break;
    if (text[i] === "[") {
      const arrayTable = text[i + 1] === "[";
      i += arrayTable ? 2 : 1;
      const path = parseKey();
      if (text[i] !== "]" || arrayTable && text[i + 1] !== "]") fail2("expected ] after table name");
      i += arrayTable ? 2 : 1;
      current = tableAt(path, arrayTable);
      continue;
    }
    const key = parseKey();
    if (text[i] !== "=") fail2("expected =");
    i++;
    setPath(current, key, parseValue());
    ws();
    if (text[i] === "#") while (i < n && text[i] !== "\n") i++;
    if (i < n && text[i] !== "\n" && text[i] !== "\r") fail2("expected end of line");
  }
  return root;
}
function routesOf(cfg) {
  const list = [];
  if (cfg.route !== void 0) list.push(cfg.route);
  if (Array.isArray(cfg.routes)) list.push(...cfg.routes);
  return list.flatMap((r) => {
    if (typeof r === "string") return [{ pattern: r, customDomain: false }];
    if (r && typeof r === "object" && typeof r.pattern === "string") {
      return [{ pattern: r.pattern, customDomain: r.custom_domain === true }];
    }
    return [];
  });
}
function ratelimitsOf(cfg) {
  const out = [];
  for (const b of Array.isArray(cfg.ratelimits) ? cfg.ratelimits : []) {
    if (b?.namespace_id !== void 0) out.push({ binding: String(b.name ?? ""), namespaceId: String(b.namespace_id) });
  }
  for (const b of Array.isArray(cfg.unsafe?.bindings) ? cfg.unsafe.bindings : []) {
    if (b?.type === "ratelimit" && b.namespace_id !== void 0) out.push({ binding: String(b.name ?? ""), namespaceId: String(b.namespace_id) });
  }
  return out;
}
var bool = (v) => typeof v === "boolean" ? v : void 0;
function cronsOf(c) {
  const list = c?.triggers?.crons;
  return Array.isArray(list) ? list.filter((x) => typeof x === "string") : void 0;
}
function workersFromConfig(cfg, file, authMarkers = []) {
  const name = typeof cfg.name === "string" ? cfg.name : void 0;
  if (!name) return [];
  const make = (c, workerName, env, parent) => {
    const routes = routesOf(c);
    const inherited = parent && routes.length === 0 && c.route === void 0 && c.routes === void 0 ? routesOf(parent) : routes;
    const workersDev = bool(c.workers_dev) ?? (parent ? bool(parent.workers_dev) : void 0);
    const previewUrls = bool(c.preview_urls) ?? (parent ? bool(parent.preview_urls) : void 0);
    const compat = c.compatibility_date ?? parent?.compatibility_date;
    const crons = cronsOf(c) ?? cronsOf(parent);
    return {
      name: workerName,
      file,
      ...env ? { env } : {},
      ...compat ? { compatibilityDate: String(compat) } : {},
      ...workersDev !== void 0 ? { workersDev } : {},
      ...previewUrls !== void 0 ? { previewUrls } : {},
      routes: inherited,
      ratelimitNamespaces: ratelimitsOf(c),
      authMarkers,
      ...crons?.length ? { crons } : {}
    };
  };
  const out = [make(cfg, name)];
  if (cfg.env && typeof cfg.env === "object") {
    for (const [env, ec] of Object.entries(cfg.env)) {
      if (!ec || typeof ec !== "object") continue;
      out.push(make(ec, typeof ec.name === "string" ? ec.name : `${name}-${env}`, env, cfg));
    }
  }
  return out;
}
function parseWranglerFile(file, text, authMarkers = []) {
  const cfg = file.endsWith(".toml") ? parseToml(text) : parseJsonc(text);
  return workersFromConfig(cfg, file, authMarkers);
}
var DEFAULT_AUTH_MARKERS = [
  { label: "Access JWT check", pattern: "cf-access-jwt-assertion" },
  { label: "passkey / WebAuthn", pattern: "navigator\\.credentials|webauthn|passkey" },
  { label: "sign-in route", pattern: "['\"`]/(login|signin|sign-in|auth/callback)['\"`/]" },
  { label: "email allowlist", pattern: "allowed_emails" },
  { label: "basic auth", pattern: "www-authenticate" }
];

// ../flare/src/node/scan.ts
var CONFIG_NAMES = ["wrangler.jsonc", "wrangler.json", "wrangler.toml"];
var SKIP_DIRS = /* @__PURE__ */ new Set(["node_modules", ".git", "dist", "build", ".wrangler", ".next", ".turbo", "coverage", ".venv", "vendor"]);
var SOURCE_EXT = /\.(ts|tsx|js|mjs|jsx|cjs)$/;
var MAX_DEPTH = 4;
var MAX_SOURCE_FILES = 800;
var MAX_FILE_BYTES = 1e6;
function expandHome(p) {
  return p === "~" ? homedir() : p.startsWith("~/") ? join(homedir(), p.slice(2)) : p;
}
async function expandRepoArgs(args) {
  const out = [];
  for (const raw of args) {
    const p = resolve(expandHome(raw));
    if (basename(p) === "*") {
      const parent = dirname(p);
      try {
        for (const e of await readdir(parent, { withFileTypes: true })) if (e.isDirectory() && !e.name.startsWith(".")) out.push(join(parent, e.name));
      } catch {
      }
    } else out.push(p);
  }
  return [...new Set(out)];
}
async function findConfigs(dir, depth = 0) {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  const found = [];
  const here = CONFIG_NAMES.find((n) => entries.some((e) => e.isFile() && e.name === n));
  if (here) found.push(join(dir, here));
  if (depth >= MAX_DEPTH) return found;
  for (const e of entries) {
    if (e.isDirectory() && !SKIP_DIRS.has(e.name) && !e.name.startsWith(".")) found.push(...await findConfigs(join(dir, e.name), depth + 1));
  }
  return found;
}
async function sourceFiles(dir, acc = [], depth = 0) {
  if (acc.length >= MAX_SOURCE_FILES || depth > 8) return acc;
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return acc;
  }
  for (const e of entries) {
    if (acc.length >= MAX_SOURCE_FILES) break;
    const p = join(dir, e.name);
    if (e.isDirectory() && !SKIP_DIRS.has(e.name) && !e.name.startsWith(".")) await sourceFiles(p, acc, depth + 1);
    else if (e.isFile() && SOURCE_EXT.test(e.name) && !e.name.endsWith(".d.ts") && !/\.(test|spec)\./.test(e.name)) acc.push(p);
  }
  return acc;
}
var handlerRe = (name) => new RegExp(
  `(?:^|[\\s,{;])(?:async\\s+)?${name}\\s*(?:\\([^)]*\\)\\s*(?::\\s*[^{;=]+)?\\{|:\\s*(?:async\\s+)?(?:function\\b|\\(|[A-Za-z_$][\\w$.]*\\s*[,}\\n]))|[{,]\\s*${name}\\s*[,}]|addEventListener\\(\\s*['"\`]${name}['"\`]`,
  "m"
);
var FETCH_RE = handlerRe("fetch");
var SCHEDULED_RE = handlerRe("scheduled");
var OPAQUE_DEFAULT_RE = /export\s+default\s+(?!\{|class\b|async\b|function\b)[A-Za-z_$]/;
async function scanSource(dir, markers = DEFAULT_AUTH_MARKERS) {
  const res = markers.map((m) => ({ label: m.label, re: new RegExp(m.pattern, "i") }));
  const hit = /* @__PURE__ */ new Set();
  const entry = { fetch: false, scheduled: false, opaqueDefault: false };
  let read = 0;
  for (const f of await sourceFiles(dir)) {
    try {
      if ((await stat(f)).size > MAX_FILE_BYTES) continue;
      const text = await readFile2(f, "utf8");
      read++;
      for (const m of res) if (!hit.has(m.label) && m.re.test(text)) hit.add(m.label);
      entry.fetch ||= FETCH_RE.test(text);
      entry.scheduled ||= SCHEDULED_RE.test(text);
      entry.opaqueDefault ||= OPAQUE_DEFAULT_RE.test(text);
    } catch {
    }
  }
  return { markers: [...hit], ...read ? { entry } : {} };
}
async function scanRepos(repos, opts = {}) {
  const workers = [];
  const gaps = [];
  const files = [];
  const base = opts.base ?? homedir();
  for (const repo of await expandRepoArgs(repos)) {
    for (const file of await findConfigs(repo)) {
      const shown = relative(base, file).startsWith("..") ? file : `~/${relative(base, file)}`;
      files.push(shown);
      try {
        const text = await readFile2(file, "utf8");
        const src = await scanSource(dirname(file), opts.markers);
        workers.push(...parseWranglerFile(shown, text, src.markers).map((w) => ({ ...w, file: shown, ...src.entry ? { entry: src.entry } : {} })));
      } catch (e) {
        gaps.push({ account: "local", what: shown, reason: `could not parse: ${e instanceof Error ? e.message : String(e)}` });
      }
    }
  }
  if (repos.length && files.length === 0) gaps.push({ account: "local", what: repos.join(" "), reason: "no wrangler.jsonc, wrangler.json or wrangler.toml found" });
  return { workers, gaps, files };
}

// ../flare/src/node/state.ts
import { mkdir, readFile as readFile3, writeFile } from "node:fs/promises";
import { dirname as dirname2 } from "node:path";
async function loadState(file) {
  try {
    const s = JSON.parse(await readFile3(file, "utf8"));
    return s.version === 1 && s.secrets && typeof s.secrets === "object" ? s : void 0;
  } catch {
    return void 0;
  }
}
async function saveState(file, secrets, now) {
  await mkdir(dirname2(file), { recursive: true });
  const s = { version: 1, savedAt: now.toISOString(), secrets };
  await writeFile(file, JSON.stringify(s, null, 2) + "\n", { mode: 384 });
}

// ../flare/src/main.ts
var HELP = `${BRAND.fullName}: read-only audit of Cloudflare accounts and Workers.

Usage: ${BRAND.cli} [options] [--repos <dir>...]

Tokens are read from environment variables only (never from argv):
  CF_API_TOKEN or CLOUDFLARE_API_TOKEN by default, or every --token-env NAME given.

Options:
  --token-env NAME        Env var holding a token; repeat for several accounts/tokens
  --account ID            Only audit this account id (repeatable); default: all the token sees
  --repos DIR...          Scan wrangler.toml/json/jsonc under these dirs ("~/dev/*" works)
  --no-api                Local wrangler files only; no Cloudflare calls
  --config FILE           Config file (default ./flare.config.json if present)
  --public HOST           Hostname meant to be public (repeatable; "*.example.com" ok)
  --stale-days N          Dead-script threshold (default ${DEFAULT_OPTIONS.staleDays})
  --compat-months N       Old compatibility_date threshold (default ${DEFAULT_OPTIONS.compatMonths})
  --shallow               Skip per-script calls (faster; no workers.dev/bindings/secrets data)
  --json [FILE]           JSON to FILE, or to stdout instead of the table
  --html FILE             Write the self-contained HTML report
  --state FILE            Secret-name baseline (default ~/.${BRAND.cli}/state.json)
  --no-state              Do not read or write the baseline
  --snapshot-out FILE     Save the collected data (no secret values) for replay
  --snapshot-in FILE      Audit a saved snapshot instead of calling the API (as of its takenAt)
  --summary FILE          Append the findings as a Markdown table (CI job summary)
  --ingest-out FILE       Write the dawnfix.flare/1 counts document: counts per check and
                          severity and hashed account ids, no names (schema/flare-ingest.schema.json)
  --fail-on LEVEL         Exit 1 when a finding is at/above LEVEL: ${SEVERITIES.join("|")}|never (default high)
  --no-color              Plain table
  -h, --help              This help
`;
async function main(argv, io2) {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      allowPositionals: true,
      options: {
        "token-env": { type: "string", multiple: true },
        account: { type: "string", multiple: true },
        repos: { type: "string", multiple: true },
        "no-api": { type: "boolean" },
        config: { type: "string" },
        public: { type: "string", multiple: true },
        "stale-days": { type: "string" },
        "compat-months": { type: "string" },
        shallow: { type: "boolean" },
        json: { type: "boolean" },
        html: { type: "string" },
        state: { type: "string" },
        "no-state": { type: "boolean" },
        "snapshot-out": { type: "string" },
        "snapshot-in": { type: "string" },
        summary: { type: "string" },
        "ingest-out": { type: "string" },
        "fail-on": { type: "string" },
        "no-color": { type: "boolean" },
        help: { type: "boolean", short: "h" }
      }
    });
  } catch (e) {
    io2.stderr(`${e instanceof Error ? e.message : String(e)}

${HELP}`);
    return 2;
  }
  const v = parsed.values;
  if (v.help) {
    io2.stdout(HELP);
    return 0;
  }
  let jsonFile;
  const positionals = [...parsed.positionals];
  if (v.json) {
    const at = argv.indexOf("--json");
    const next = argv[at + 1];
    if (next && !next.startsWith("-") && next.endsWith(".json") && positionals.includes(next)) {
      jsonFile = next;
      positionals.splice(positionals.indexOf(next), 1);
    }
  }
  try {
    const defaultConfig = join2(io2.cwd, "flare.config.json");
    const cfgFile = v.config ? resolve2(io2.cwd, expandHome(v.config)) : existsSync(defaultConfig) ? defaultConfig : void 0;
    const cfg = await loadConfig(cfgFile, Boolean(v.config));
    const failOn = v["fail-on"] ?? cfg.failOn ?? "high";
    if (failOn !== "never" && !SEVERITIES.includes(failOn)) throw new Error(`--fail-on must be one of ${SEVERITIES.join(", ")}, never`);
    const num = (s, d, name) => {
      if (s === void 0) return d;
      const n = Number(s);
      if (!Number.isFinite(n) || n <= 0) throw new Error(`${name} must be a positive number`);
      return n;
    };
    let now = io2.now();
    const repos = [...v.repos ?? [], ...positionals, ...v.repos || positionals.length ? [] : cfg.repos ?? []];
    let snapshot;
    if (v["snapshot-in"]) {
      snapshot = JSON.parse(await readFile4(resolve2(io2.cwd, v["snapshot-in"]), "utf8"));
      const taken = new Date(snapshot.takenAt);
      if (!Number.isNaN(taken.getTime())) now = taken;
    } else {
      const local = repos.length ? await scanRepos(repos, cfg.authMarkers ? { markers: cfg.authMarkers } : {}) : { workers: [], gaps: [], files: [] };
      const tokenEnv = v["token-env"] ?? cfg.tokenEnv ?? ["CF_API_TOKEN", "CLOUDFLARE_API_TOKEN"];
      const tokens = v["no-api"] ? [] : [...new Set(tokenEnv.map((n) => io2.env[n]).filter((t) => Boolean(t)))];
      if (!v["no-api"] && tokens.length === 0) {
        if (!repos.length) throw new Error(`no token: set ${tokenEnv.join(" or ")}, or pass --no-api with --repos`);
        io2.stderr(`No token in ${tokenEnv.join("/")}; auditing local files only.
`);
      }
      const accountIds = v.account ?? cfg.accounts;
      const collected = await collectSnapshot({
        tokens,
        fetch: io2.fetch,
        local: local.workers,
        collect: { ...accountIds?.length ? { accountIds } : {}, ...v.shallow ? { shallow: true } : {} },
        now
      });
      snapshot = collected.snapshot;
      snapshot.localGaps.push(...local.gaps);
    }
    if (v["snapshot-out"]) await writeFile2(resolve2(io2.cwd, v["snapshot-out"]), JSON.stringify(snapshot, null, 2) + "\n", { mode: 384 });
    const stateFile = resolve2(io2.cwd, expandHome(v.state ?? join2(homedir2(), `.${BRAND.cli}`, "state.json")));
    const useState = !v["no-state"] && !v["snapshot-in"];
    const prev = useState ? await loadState(stateFile) : void 0;
    const { result, secretsBaseline } = audit(snapshot, {
      publicHostnames: [...cfg.publicHostnames ?? [], ...v.public ?? []],
      appAuthScripts: cfg.appAuthScripts ?? [],
      staleDays: num(v["stale-days"], cfg.staleDays ?? DEFAULT_OPTIONS.staleDays, "--stale-days"),
      compatMonths: num(v["compat-months"], cfg.compatMonths ?? DEFAULT_OPTIONS.compatMonths, "--compat-months"),
      ...prev ? { secretsBaseline: prev.secrets } : {},
      now
    });
    if (useState && Object.keys(secretsBaseline).length) await saveState(stateFile, secretsBaseline, now);
    if (v.html) {
      await writeFile2(resolve2(io2.cwd, v.html), renderHtml(result));
      io2.stderr(`HTML report: ${resolve2(io2.cwd, v.html)}
`);
    }
    if (v.summary) await appendFile(resolve2(io2.cwd, v.summary), renderMarkdown(result));
    if (v["ingest-out"]) await writeFile2(resolve2(io2.cwd, v["ingest-out"]), JSON.stringify(await ingestDoc(result), null, 2) + "\n");
    const json = JSON.stringify({ ...result, pitch: BRAND.pitch }, null, 2) + "\n";
    if (v.json && jsonFile) await writeFile2(resolve2(io2.cwd, jsonFile), json);
    if (v.json && !jsonFile) io2.stdout(json);
    else io2.stdout(renderText(result, { color: io2.isTTY && !v["no-color"] && !io2.env.NO_COLOR, ...io2.columns ? { width: io2.columns } : {} }));
    return failsAt(result, failOn) ? 1 : 0;
  } catch (e) {
    io2.stderr(`${BRAND.cli}: ${e instanceof Error ? e.message : String(e)}
`);
    return 2;
  }
}

// src/doctor.mjs
var import_yaml = __toESM(require_dist(), 1);
import { execFileSync as execFileSync2 } from "node:child_process";
import { existsSync as existsSync3, readdirSync, readFileSync } from "node:fs";
import { join as join4 } from "node:path";
import { parseArgs as parseArgs2 } from "node:util";

// ../core/schema/config.schema.json
var config_schema_default = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  $id: "https://dawnfix.dev/schema/config.schema.json",
  title: ".dawnfix.yml",
  description: "What Dawnfix watches and what it may do. dawnfix_core.config is the authority; this schema says the same in JSON Schema for editors and `npx dawnfix doctor`, and core/tests/test_config_schema.py keeps the two in step. Checks a schema cannot express (duplicate sources, a regex that does not compile) are left to `dawnfix validate`.",
  type: "object",
  additionalProperties: false,
  required: ["version", "sources"],
  properties: {
    version: { const: 1, description: "Only version 1 is supported" },
    autonomy: { enum: ["diagnose", "plan", "draft-pr"], default: "diagnose" },
    schedule: {
      type: "string",
      pattern: "^\\s*\\S+(\\s+\\S+){4}\\s*$",
      description: "A 5-field cron expression; copy it into the workflow's cron as well",
      default: "17 * * * *"
    },
    sources: {
      type: "array",
      minItems: 1,
      items: {
        type: "object",
        minProperties: 1,
        maxProperties: 1,
        additionalProperties: false,
        properties: {
          aws: { $ref: "#/$defs/aws" },
          gcp: { $ref: "#/$defs/gcp" }
        }
      }
    },
    rules: { type: "array", items: { $ref: "#/$defs/rule" } },
    limits: {
      type: "object",
      additionalProperties: false,
      properties: {
        fix_prs_per_day: { $ref: "#/$defs/whole" },
        max_turns: { $ref: "#/$defs/whole" },
        timeout_minutes: { $ref: "#/$defs/whole" },
        max_events_per_source: { $ref: "#/$defs/whole" },
        max_findings: { type: "integer", exclusiveMinimum: 0, maximum: 150 },
        spike_factor: { type: "number", exclusiveMinimum: 0 },
        spike_min_count: { $ref: "#/$defs/whole" }
      }
    },
    phi_mode: { type: "boolean" },
    report: {
      type: "object",
      additionalProperties: false,
      properties: {
        issues: { enum: ["github", "linear", "jira", "none"] },
        digest: { type: "array", items: { type: "string", pattern: "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$" } }
      }
    },
    test: {
      type: "object",
      additionalProperties: false,
      properties: {
        command: {
          type: "string",
          maxLength: 200,
          pattern: "^[A-Za-z0-9_./:=@+-]+( [A-Za-z0-9_./:=@+-]+)*$",
          description: "The one command the fix agent may run: plain words, no quotes or shell operators"
        }
      }
    },
    extends: { not: {}, description: "Not implemented yet" }
  },
  $defs: {
    whole: { type: "integer", exclusiveMinimum: 0 },
    aws: {
      type: "object",
      additionalProperties: false,
      required: ["region"],
      properties: {
        region: { type: "string", pattern: "^[a-z]{2}(-[a-z]+)+-[0-9]$" },
        role: { type: "string", pattern: "^arn:aws[a-z-]*:iam::[0-9]{1,12}:role/[A-Za-z0-9_+=,.@/-]+$" },
        log_groups: {
          type: "array",
          items: {
            anyOf: [
              { type: "string", minLength: 1, pattern: "\\S" },
              {
                type: "object",
                additionalProperties: false,
                required: ["name"],
                properties: {
                  name: { type: "string", minLength: 1, pattern: "\\S" },
                  filter_pattern: { type: "string" },
                  stream_prefix: { type: "string" }
                }
              }
            ]
          }
        },
        alarms: { type: "boolean" },
        alb: { type: "string", pattern: "^app/[A-Za-z0-9_-]+/[A-Za-z0-9_*-]+$" }
      },
      anyOf: [
        { required: ["log_groups"], properties: { log_groups: { minItems: 1 } } },
        { required: ["alarms"], properties: { alarms: { const: true } } },
        { required: ["alb"] }
      ]
    },
    gcp: {
      type: "object",
      additionalProperties: false,
      required: ["project"],
      properties: {
        project: { type: "string", pattern: "^[a-z][a-z0-9-]{4,28}[a-z0-9]$" },
        filter: { type: "string", minLength: 1, pattern: "\\S" }
      }
    },
    rule: {
      type: "object",
      additionalProperties: false,
      required: ["name", "conditions", "actions"],
      properties: {
        name: { type: "string", minLength: 1, maxLength: 64, pattern: "\\S" },
        conditions: {
          type: "array",
          minItems: 1,
          items: {
            type: "string",
            pattern: "^\\s*(source|source_id|kind|service|route|method|status|error|error_class|alarm|count|severity|fingerprint)\\s*(==|!=|~=|\\^=|\\$=|>=|<=|>|<)\\s*\\S"
          }
        },
        actions: {
          type: "array",
          minItems: 1,
          items: {
            anyOf: [
              { const: "ignore" },
              {
                type: "object",
                additionalProperties: false,
                required: ["severity"],
                properties: { severity: { enum: ["critical", "high", "medium", "low"] } }
              },
              {
                type: "object",
                additionalProperties: false,
                required: ["notify"],
                properties: {
                  notify: {
                    anyOf: [
                      { enum: ["email", "issue", "none"] },
                      { type: "array", items: { enum: ["email", "issue", "none"] } }
                    ]
                  }
                }
              }
            ]
          }
        }
      }
    }
  }
};

// src/repo.mjs
import { execFileSync } from "node:child_process";
import { existsSync as existsSync2 } from "node:fs";
import { join as join3 } from "node:path";
function git(cwd, ...args) {
  try {
    return execFileSync("git", args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return "";
  }
}
function slugFromRemote(url) {
  const m = /github\.com[:/]+([A-Za-z0-9][A-Za-z0-9-]*)\/([A-Za-z0-9_.-]+?)(?:\.git)?\/?$/.exec(url || "");
  return m ? `${m[1]}/${m[2]}` : "";
}
function detectRepo(cwd) {
  const root = git(cwd, "rev-parse", "--show-toplevel");
  if (!root) return null;
  const slug = slugFromRemote(git(root, "remote", "get-url", "origin"));
  const head = git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").replace(/^origin\//, "");
  const branch = head || git(root, "symbolic-ref", "--short", "HEAD") || "main";
  return { root, slug, branch };
}
function detectCommands(root) {
  const has = (f) => existsSync2(join3(root, f));
  if (has("package.json")) {
    const install = has("pnpm-lock.yaml") ? "pnpm install --frozen-lockfile" : has("yarn.lock") ? "yarn install --frozen-lockfile" : has("package-lock.json") ? "npm ci" : "npm install";
    const test = has("pnpm-lock.yaml") ? "pnpm test" : has("yarn.lock") ? "yarn test" : "npm test";
    return { test, install };
  }
  if (has("pyproject.toml") || has("requirements.txt")) {
    return { test: "python -m pytest -q", install: has("requirements.txt") ? "pip install -r requirements.txt" : "pip install -e ." };
  }
  if (has("go.mod")) return { test: "go test ./...", install: "go mod download" };
  if (has("Cargo.toml")) return { test: "cargo test", install: "cargo fetch" };
  if (has("Gemfile")) return { test: "bundle exec rake test", install: "bundle install" };
  return { test: "", install: "" };
}

// src/schema.mjs
var KEYWORDS = /* @__PURE__ */ new Set([
  "$schema",
  "$id",
  "$ref",
  "$defs",
  "title",
  "description",
  "default",
  "type",
  "const",
  "enum",
  "required",
  "properties",
  "additionalProperties",
  "items",
  "minItems",
  "minProperties",
  "maxProperties",
  "minLength",
  "maxLength",
  "pattern",
  "exclusiveMinimum",
  "maximum",
  "anyOf",
  "not"
]);
function typeOf(v) {
  if (v === null) return "null";
  if (Array.isArray(v)) return "array";
  if (typeof v === "number") return Number.isInteger(v) ? "integer" : "number";
  return typeof v;
}
function typeOk(want, v) {
  const t = typeOf(v);
  return t === want || want === "number" && t === "integer";
}
var show = (v) => JSON.stringify(v);
function validate(schema, value, root = schema, path = "") {
  for (const k of Object.keys(schema)) {
    if (!KEYWORDS.has(k)) throw new Error(`schema keyword ${k} is not supported by this validator`);
  }
  const errs = [];
  const at = path || "/";
  if (schema.$ref) {
    const name = schema.$ref.replace(/^#\/\$defs\//, "");
    errs.push(...validate(root.$defs[name], value, root, path));
  }
  if (schema.type && !typeOk(schema.type, value)) {
    errs.push({ path: at, message: `expected ${schema.type}, got ${typeOf(value)}` });
    return errs;
  }
  if ("const" in schema && value !== schema.const) errs.push({ path: at, message: `must be ${show(schema.const)}` });
  if (schema.enum && !schema.enum.includes(value)) {
    errs.push({ path: at, message: `must be one of ${schema.enum.join(", ")}, got ${show(value)}` });
  }
  if (schema.not && validate(schema.not, value, root, path).length === 0) {
    errs.push({ path: at, message: schema.description || "not allowed" });
  }
  if (typeOf(value) === "string") {
    if (schema.minLength !== void 0 && value.length < schema.minLength) errs.push({ path: at, message: "must not be empty" });
    if (schema.maxLength !== void 0 && value.length > schema.maxLength) {
      errs.push({ path: at, message: `at most ${schema.maxLength} characters` });
    }
    if (schema.pattern && !new RegExp(schema.pattern, "u").test(value)) {
      errs.push({ path: at, message: `${show(value.slice(0, 60))} is not valid${schema.description ? `: ${schema.description}` : ""}` });
    }
  }
  if (typeof value === "number") {
    if (schema.exclusiveMinimum !== void 0 && !(value > schema.exclusiveMinimum)) {
      errs.push({ path: at, message: `must be greater than ${schema.exclusiveMinimum}` });
    }
    if (schema.maximum !== void 0 && value > schema.maximum) errs.push({ path: at, message: `at most ${schema.maximum}` });
  }
  if (typeOf(value) === "object") {
    const keys = Object.keys(value);
    for (const r of schema.required || []) {
      if (!(r in value)) errs.push({ path: at, message: `missing required key ${r}` });
    }
    if (schema.minProperties !== void 0 && keys.length < schema.minProperties) {
      errs.push({ path: at, message: `needs at least ${schema.minProperties} key(s)` });
    }
    if (schema.maxProperties !== void 0 && keys.length > schema.maxProperties) {
      errs.push({ path: at, message: `at most ${schema.maxProperties} key(s), got ${keys.join(", ")}` });
    }
    for (const k of keys) {
      if (schema.properties && k in schema.properties) {
        errs.push(...validate(schema.properties[k], value[k], root, `${path}/${k}`));
      } else if (schema.additionalProperties === false) {
        const allowed = Object.keys(schema.properties || {}).join(", ");
        errs.push({ path: at, message: `unknown key ${k} (allowed: ${allowed})` });
      }
    }
  }
  if (Array.isArray(value)) {
    if (schema.minItems !== void 0 && value.length < schema.minItems) {
      errs.push({ path: at, message: schema.minItems === 1 ? "must not be empty" : `needs at least ${schema.minItems} items` });
    }
    if (schema.items) value.forEach((v, i) => errs.push(...validate(schema.items, v, root, `${path}/${i}`)));
  }
  if (schema.anyOf) {
    const tries = schema.anyOf.map((s) => validate(s, value, root, path));
    if (!tries.some((t) => t.length === 0)) {
      const typed = schema.anyOf.map((s, i) => [s, tries[i]]).filter(([s]) => !s.type || typeOk(s.type, value));
      if (typed.length === 1 && typed[0][0].type) errs.push(...typed[0][1]);
      else errs.push({ path: at, message: schema.description || "does not match any allowed form" });
    }
  }
  return errs;
}

// src/version.mjs
var VERSION = true ? "0.3.1" : "0.0.0-dev";
var TAG = `v${VERSION}`;
var MAJOR_REF = `v${VERSION.split(".")[0]}`;
var REPO_URL = "https://github.com/dawnfix/dawnfix";
var RAW = `https://raw.githubusercontent.com/dawnfix/dawnfix/${TAG}`;

// src/doctor.mjs
var DOCTOR_HELP = `Usage: dawnfix doctor [--dir DIR] [--no-gh]

Checks the Dawnfix setup of the repo you are in:
  - .dawnfix.yml is valid (core's schema)
  - .github/workflows/ calls dawnfix/dawnfix/.github/workflows/dawnfix.yml at a pinned
    release (a tag such as v0 or v${VERSION}, or a commit SHA), or holds the copy-it-yourself
    template, with the permissions its jobs need and the cron of .dawnfix.yml
  - the secrets and variables it uses exist (names only, through gh; --no-gh lists them)
  - Free or Enterprise: whether an Enterprise key is set
Exit 0 when nothing failed, 1 otherwise.
`;
var NEEDED_PERMISSIONS = { contents: "write", "pull-requests": "write", issues: "write", "id-token": "write" };
var USES = /^dawnfix\/dawnfix\/\.github\/workflows\/dawnfix\.yml(?:@(.*))?$/;
var ENTERPRISE = ["DAWNFIX_ENTERPRISE_KEY"];
function readYaml(path) {
  return (0, import_yaml.parse)(readFileSync(path, "utf8"));
}
function findWorkflow(root) {
  const dir = join4(root, ".github", "workflows");
  if (!existsSync3(dir)) return null;
  for (const f of readdirSync(dir).filter((n) => /\.ya?ml$/.test(n)).sort()) {
    let doc;
    try {
      doc = readYaml(join4(dir, f));
    } catch {
      continue;
    }
    for (const [name, job] of Object.entries(doc?.jobs || {})) {
      const m = USES.exec(String(job?.uses || ""));
      if (m) return { file: `.github/workflows/${f}`, doc, kind: "caller", job: name, jobDoc: job, ref: m[1] || "" };
    }
    if (doc?.env?.DAWNFIX_VERSION && doc?.jobs?.read && doc?.jobs?.["pr-state"]) {
      return { file: `.github/workflows/${f}`, doc, kind: "template", ref: `v${doc.env.DAWNFIX_VERSION}` };
    }
  }
  return null;
}
function pinned(ref) {
  if (/^[0-9a-f]{40}$/.test(ref)) return "sha";
  if (/^v\d+\.\d+\.\d+$/.test(ref)) return "release";
  if (/^v\d+(\.\d+)?$/.test(ref)) return "major";
  return "";
}
function referenced(text) {
  const names = (kind) => [...new Set([...text.matchAll(new RegExp(`\\b${kind}\\.([A-Za-z_][A-Za-z0-9_]*)`, "g"))].map((m) => m[1]))];
  return { secrets: names("secrets"), vars: names("vars") };
}
function gh(args, cwd, env) {
  try {
    const out = execFileSync2("gh", args, { cwd, env, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 2e4 });
    return { ok: true, names: JSON.parse(out).map((x) => x.name) };
  } catch (e) {
    return { ok: false, why: e.code === "ENOENT" ? "gh is not installed" : String(e.stderr || e.message).trim().split("\n")[0] };
  }
}
function cronOf(doc) {
  const on = doc?.on ?? doc?.true;
  const s = on?.schedule;
  return Array.isArray(s) && s[0]?.cron ? String(s[0].cron) : "";
}
async function doctor(argv, io2) {
  let v;
  try {
    ({ values: v } = parseArgs2({ args: argv, options: { dir: { type: "string" }, "no-gh": { type: "boolean" }, help: { type: "boolean", short: "h" } }, strict: true }));
  } catch (e) {
    io2.stderr(`dawnfix doctor: ${e.message}

${DOCTOR_HELP}`);
    return 2;
  }
  if (v.help) {
    io2.stdout(DOCTOR_HELP);
    return 0;
  }
  let failed = 0;
  const ok = (m) => io2.stdout(`ok    ${m}
`);
  const warn = (m) => io2.stdout(`warn  ${m}
`);
  const bad = (m) => {
    failed++;
    io2.stdout(`FAIL  ${m}
`);
  };
  const repo = detectRepo(v.dir || io2.cwd);
  if (!repo) {
    io2.stderr("dawnfix doctor: not inside a git repository\n");
    return 2;
  }
  io2.stdout(`Dawnfix doctor ${VERSION}: ${repo.slug || repo.root}

`);
  const cfgPath = join4(repo.root, ".dawnfix.yml");
  let config = null;
  if (!existsSync3(cfgPath)) {
    bad(".dawnfix.yml is missing: run npx dawnfix init");
  } else {
    try {
      config = readYaml(cfgPath);
      const errors = validate(config_schema_default, config);
      if (errors.length) {
        bad(`.dawnfix.yml has ${errors.length} problem(s):`);
        for (const e of errors) io2.stdout(`        ${e.path}: ${e.message}
`);
        config = null;
      } else {
        const kinds = (config.sources || []).map((s) => Object.keys(s)[0]).join(", ");
        ok(`.dawnfix.yml is valid (${kinds}; autonomy ${config.autonomy || "diagnose"})`);
      }
    } catch (e) {
      bad(`.dawnfix.yml is not valid YAML: ${e.message.split("\n")[0]}`);
    }
  }
  const wf = findWorkflow(repo.root);
  let needs = { secrets: ["ANTHROPIC_API_KEY"], vars: [] };
  let passesKey = false;
  if (!wf) {
    bad("no Dawnfix workflow in .github/workflows/: run npx dawnfix init");
  } else {
    const text = readFileSync(join4(repo.root, wf.file), "utf8");
    if (wf.kind === "caller") {
      const kind = pinned(wf.ref);
      if (!wf.ref) bad(`${wf.file} calls dawnfix.yml without a ref: add @v0 (or a release tag or commit SHA)`);
      else if (!kind) bad(`${wf.file} calls dawnfix.yml@${wf.ref}: not pinned to a release. Use @v0, @v${VERSION} or a commit SHA`);
      else ok(`${wf.file} calls dawnfix/dawnfix@${wf.ref} (${kind === "sha" ? "a commit SHA" : kind === "release" ? "an exact release" : "the major release tag; pin v" + VERSION + " or a SHA to freeze it"})`);
      const perms = wf.jobDoc.permissions ?? wf.doc.permissions ?? {};
      const missing = Object.entries(NEEDED_PERMISSIONS).filter(([k, val]) => perms[k] !== val).map(([k, val]) => `${k}: ${val}`);
      if (perms === "write-all" || missing.length === 0) ok("permissions cover every job (each job narrows them)");
      else bad(`${wf.file} must grant ${missing.join(", ")} (GitHub refuses to start a run whose jobs ask for more than the caller grants)`);
      const wfNeeds = referenced(JSON.stringify(wf.jobDoc.with || {}) + JSON.stringify(wf.jobDoc.secrets || {}));
      needs = { secrets: [.../* @__PURE__ */ new Set(["ANTHROPIC_API_KEY", ...wfNeeds.secrets])], vars: wfNeeds.vars };
      if (wf.jobDoc.secrets === "inherit") {
        warn("secrets: inherit passes every secret of the repo to the workflow; pass ANTHROPIC_API_KEY (and DAWNFIX_ENTERPRISE_KEY) by name");
        needs.secrets = ["ANTHROPIC_API_KEY"];
      }
      passesKey = wf.jobDoc.secrets === "inherit" || ENTERPRISE.some((k) => wfNeeds.secrets.includes(k));
    } else {
      ok(`${wf.file} is the copy-it-yourself template of ${wf.ref}`);
      const r = referenced(text);
      needs = { secrets: ["ANTHROPIC_API_KEY"], vars: r.vars.filter((x) => /ROLE_ARN|WIF_PROVIDER/.test(x)) };
      passesKey = true;
    }
    const cron = cronOf(wf.doc);
    if (config && cron) {
      const want = String(config.schedule || "17 * * * *").trim().split(/\s+/).join(" ");
      if (cron.trim().split(/\s+/).join(" ") === want) ok(`cron "${cron}" matches the schedule of .dawnfix.yml`);
      else warn(`cron "${cron}" differs from the schedule "${want}" of .dawnfix.yml`);
    } else if (!cron) {
      warn(`${wf.file} has no schedule: Dawnfix only runs when started by hand`);
    }
    const sources = (config?.sources || []).map((s) => Object.keys(s)[0]);
    if (sources.includes("aws") && !/aws-role-arn|DAWNFIX_AWS_ROLE_ARN/.test(text)) bad("an AWS source but no aws-role-arn in the workflow");
    if (sources.includes("gcp") && !/gcp-wif-provider|DAWNFIX_GCP_WIF_PROVIDER/.test(text)) bad("a GCP source but no gcp-wif-provider in the workflow");
  }
  const required = needs.secrets.filter((s) => !ENTERPRISE.includes(s) && s !== "DAWNFIX_PR_TOKEN" && s !== "DAWNFIX_PR_APP_PRIVATE_KEY");
  let secretNames = null;
  if (!v["no-gh"]) {
    const args = repo.slug ? ["-R", repo.slug] : [];
    const s = gh(["secret", "list", ...args, "--json", "name"], repo.root, io2.env);
    const vars = gh(["variable", "list", ...args, "--json", "name"], repo.root, io2.env);
    if (s.ok && vars.ok) {
      secretNames = s.names;
      for (const name of required) {
        if (s.names.includes(name)) ok(`secret ${name} is set`);
        else bad(`secret ${name} is not set: gh secret set ${name}${name === "ANTHROPIC_API_KEY" ? "   (an organization secret works too)" : ""}`);
      }
      for (const name of needs.vars) {
        if (vars.names.includes(name)) ok(`variable ${name} is set`);
        else bad(`variable ${name} is not set: gh variable set ${name} --body <value>`);
      }
    } else {
      warn(`could not list the repo's secrets with gh (${s.ok ? vars.why : s.why}). Check by hand in Settings > Secrets and variables > Actions:`);
      for (const name of required) io2.stdout(`        secret ${name}
`);
      for (const name of needs.vars) io2.stdout(`        variable ${name}
`);
    }
  } else {
    warn("--no-gh: check by hand in Settings > Secrets and variables > Actions:");
    for (const name of required) io2.stdout(`        secret ${name}
`);
    for (const name of needs.vars) io2.stdout(`        variable ${name}
`);
  }
  const keySet = secretNames && ENTERPRISE.some((k) => secretNames.includes(k));
  if (keySet && passesKey) ok("plan: Enterprise. The key is set; hosted reporting is on (the hosted service checks the key)");
  else if (keySet) warn("plan: an Enterprise key is set but the workflow does not pass DAWNFIX_ENTERPRISE_KEY to dawnfix.yml");
  else if (secretNames) ok("plan: Free & source available. Everything runs in your CI; nothing is sent to the hosted service");
  else ok("plan: Free & source available, unless DAWNFIX_ENTERPRISE_KEY is set (hosted reporting, Enterprise)");
  io2.stdout(failed ? `
${failed} check(s) failed.
` : "\nAll checks passed.\n");
  return failed ? 1 : 0;
}

// src/init.mjs
var import_yaml2 = __toESM(require_dist(), 1);
import { createInterface } from "node:readline/promises";
import { parseArgs as parseArgs3 } from "node:util";

// src/safe-write.mjs
import { closeSync, constants, lstatSync, mkdirSync, openSync, realpathSync, writeSync } from "node:fs";
import { dirname as dirname3, isAbsolute, join as join5, relative as relative2, sep } from "node:path";
var UnsafePath = class extends Error {
};
function lstatOrNull(p) {
  try {
    return lstatSync(p);
  } catch (e) {
    if (e.code === "ENOENT") return null;
    throw e;
  }
}
function checkTarget(root, rel) {
  if (!rel || isAbsolute(rel) || rel.split(/[\\/]/).includes("..")) throw new UnsafePath(`${rel}: not a plain path inside the repo`);
  const realRoot = realpathSync(root);
  const full = join5(root, rel);
  const parts = rel.split(/[\\/]/);
  let cur = root;
  let exists = false;
  for (let i = 0; i < parts.length; i++) {
    cur = join5(cur, parts[i]);
    const st = lstatOrNull(cur);
    const shown = parts.slice(0, i + 1).join("/");
    if (st?.isSymbolicLink()) throw new UnsafePath(`${shown} is a symbolic link; refusing to write through it`);
    if (i < parts.length - 1 && st && !st.isDirectory()) throw new UnsafePath(`${shown} is not a directory`);
    if (i === parts.length - 1) {
      if (st && !st.isFile()) throw new UnsafePath(`${shown} exists and is not a regular file`);
      exists = Boolean(st);
    }
  }
  let parent = dirname3(full);
  while (!lstatOrNull(parent)) parent = dirname3(parent);
  const realParent = realpathSync(parent);
  if (realParent !== realRoot && !realParent.startsWith(realRoot + sep)) {
    throw new UnsafePath(`${rel}: resolves outside the repo (${relative2(realRoot, realParent)})`);
  }
  return { full, exists };
}
function safeWrite(root, rel, text, { overwrite = false } = {}) {
  const { full, exists } = checkTarget(root, rel);
  if (exists && !overwrite) throw new UnsafePath(`${rel} exists already`);
  const parts = rel.split(/[\\/]/).slice(0, -1);
  let cur = root;
  for (const p of parts) {
    cur = join5(cur, p);
    if (!lstatOrNull(cur)) mkdirSync(cur);
    if (lstatSync(cur).isSymbolicLink()) throw new UnsafePath(`${relative2(root, cur)} is a symbolic link; refusing to write through it`);
  }
  const { exists: nowExists } = checkTarget(root, rel);
  const flags = constants.O_WRONLY | constants.O_NOFOLLOW | (nowExists ? constants.O_TRUNC : constants.O_CREAT | constants.O_EXCL);
  if (nowExists && !overwrite) throw new UnsafePath(`${rel} exists already`);
  const fd = openSync(full, flags, 420);
  try {
    writeSync(fd, text);
  } finally {
    closeSync(fd);
  }
}

// src/init.mjs
var INIT_HELP = `Usage: dawnfix init [options]

Sets Dawnfix up in the git repo you are in: shows .dawnfix.yml and
.github/workflows/dawnfix.yml in full, writes them when you confirm (or with --yes),
and prints the commands you run next (the read-only cloud role, gh secret set).
It never asks for a secret and never writes one.

Options:
  --cloud aws|gcp            Where the logs are (asked if missing; default aws)
  --aws-region REGION        Region of the log groups (default us-east-1)
  --log-group NAME           CloudWatch log group to watch (repeatable)
  --alarms / --no-alarms     Also report CloudWatch alarms in ALARM (default: on when no log group)
  --aws-role-arn ARN         The read-only role, if it exists already (else a repo variable)
  --gcp-project ID           GCP project whose Cloud Logging is read
  --gcp-wif-provider NAME    Workload identity provider, if it exists already (else a repo variable)
  --autonomy LEVEL           diagnose | plan | draft-pr (default diagnose: issues only)
  --test-command CMD         The one command the fix agent may run (plan, draft-pr)
  --install-command CMD      Installs dependencies before the fix agent runs (plan, draft-pr)
  --schedule CRON            When the read job runs (default "17 * * * *", hourly)
  --ref REF                  Ref of dawnfix/dawnfix to call (default ${MAJOR_REF}; a tag or commit SHA)
  --enterprise               Also send closed-PR events (hosted PR tracking, Enterprise key)
  --dir DIR                  The repo (default: the current directory)
  --yes, -y                  Write without asking
  --dry-run                  Show the files and the next steps; write nothing
  --force                    Replace files that exist
  -h, --help                 This help
`;
var OPTIONS = {
  cloud: { type: "string" },
  "aws-region": { type: "string" },
  "log-group": { type: "string", multiple: true },
  alarms: { type: "boolean" },
  "no-alarms": { type: "boolean" },
  "aws-role-arn": { type: "string" },
  "gcp-project": { type: "string" },
  "gcp-wif-provider": { type: "string" },
  autonomy: { type: "string" },
  "test-command": { type: "string" },
  "install-command": { type: "string" },
  schedule: { type: "string" },
  ref: { type: "string" },
  enterprise: { type: "boolean" },
  dir: { type: "string" },
  yes: { type: "boolean", short: "y" },
  "dry-run": { type: "boolean" },
  force: { type: "boolean" },
  help: { type: "boolean", short: "h" }
};
var q = (s) => JSON.stringify(String(s));
function renderConfig(a) {
  const lines = [
    "# .dawnfix.yml: what Dawnfix watches and what it may do. Written by `npx dawnfix init`.",
    `# Every key: ${REPO_URL}/blob/${TAG}/templates/dawnfix.yml`,
    "# Check it with: npx dawnfix doctor",
    "version: 1",
    "",
    "# diagnose: an issue per new error | plan: an issue with the planned fix | draft-pr: draft PRs.",
    `autonomy: ${a.autonomy}`,
    "",
    "# Keep it equal to the cron in .github/workflows/dawnfix.yml. Off the hour.",
    `schedule: ${q(a.schedule)}`,
    "",
    "sources:"
  ];
  if (a.cloud === "aws") {
    lines.push("  - aws:", `      region: ${a.awsRegion}`);
    if (a.logGroups.length) lines.push("      log_groups:", ...a.logGroups.map((g) => `        - ${q(g)}`));
    if (a.alarms) lines.push("      alarms: true                 # alarms currently in ALARM");
  } else {
    lines.push("  - gcp:", `      project: ${a.gcpProject}`, "      filter: 'severity>=ERROR'");
  }
  if (a.testCommand) {
    lines.push(
      "",
      "# The one command the fix agent may run (its only shell permission). Plain words only.",
      "test:",
      `  command: ${q(a.testCommand)}`
    );
  }
  lines.push("", "report:", "  issues: github", "");
  return lines.join("\n");
}
function renderCaller(a) {
  const withLines = [];
  if (a.cloud === "aws") withLines.push(`aws-role-arn: ${a.awsRoleArn || "${{ vars.DAWNFIX_AWS_ROLE_ARN }}"}`);
  else withLines.push(`gcp-wif-provider: ${a.gcpWifProvider || "${{ vars.DAWNFIX_GCP_WIF_PROVIDER }}"}`);
  if (a.installCommand) withLines.push(`install-command: ${q(a.installCommand)}`);
  return [
    `# Dawnfix (${REPO_URL}), written by \`npx dawnfix init\`. The jobs are in the`,
    "# reusable workflow below; each asks for less than the permissions granted here.",
    "name: dawnfix",
    "on:",
    `  schedule: [{ cron: ${q(a.schedule)} }] # the \`schedule\` of .dawnfix.yml`,
    "  workflow_dispatch: { inputs: { baseline: { type: boolean }, dry_run: { type: boolean } } }",
    ...a.enterprise ? ["  pull_request: { types: [closed] } # hosted PR tracking (Enterprise)"] : [],
    "permissions: { contents: write, pull-requests: write, issues: write, id-token: write }",
    "jobs:",
    "  dawnfix:",
    `    uses: dawnfix/dawnfix/.github/workflows/dawnfix.yml@${a.ref}`,
    "    with:",
    ...withLines.map((l) => `      ${l}`),
    "    secrets:",
    "      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}",
    "      DAWNFIX_ENTERPRISE_KEY: ${{ secrets.DAWNFIX_ENTERPRISE_KEY }} # optional",
    ""
  ].join("\n");
}
function nextSteps(a, repo) {
  const [org, name] = (repo.slug || "OWNER/REPO").split("/");
  const out = ["Next steps. You run these; dawnfix never asks for or stores a secret.", ""];
  let n = 1;
  if (a.cloud === "aws") {
    out.push(
      `${n++}. The read-only AWS role (CloudFormation; logs and alarms read only, trusts only ${org}/${name} on ${repo.branch}):`,
      `   ${REPO_URL}/blob/${TAG}/infra/aws/dawnfix-read-role.yaml`,
      `   curl -fsSLO ${RAW}/infra/aws/dawnfix-read-role.yaml`,
      "   aws cloudformation deploy --template-file dawnfix-read-role.yaml \\",
      `     --stack-name dawnfix-read-${name} --capabilities CAPABILITY_NAMED_IAM \\`,
      `     --parameter-overrides GitHubOrg=${org} GitHubRepo=${name} Branch=${repo.branch} \\`,
      `       CreateOIDCProvider=true RoleName=dawnfix-read-${name} LogGroupPrefix='*'`,
      `   (The account has GitHub's OIDC provider already? CreateOIDCProvider=false and`,
      `   ExistingOIDCProviderArn=<its ARN>: ${REPO_URL}/blob/${TAG}/infra/aws/README.md)`
    );
    if (!a.awsRoleArn) {
      out.push(
        `   gh variable set DAWNFIX_AWS_ROLE_ARN --body "$(aws cloudformation describe-stacks --stack-name dawnfix-read-${name} \\`,
        `     --query "Stacks[0].Outputs[?OutputKey=='RoleArn'].OutputValue" --output text)"`
      );
    }
  } else {
    out.push(
      `${n++}. Workload Identity Federation (roles/logging.viewer only, trusts only ${org}/${name} on ${repo.branch}):`,
      `   ${REPO_URL}/blob/${TAG}/infra/gcp/setup-wif.sh`,
      `   curl -fsSLO ${RAW}/infra/gcp/setup-wif.sh`,
      `   bash setup-wif.sh --branch ${repo.branch} ${a.gcpProject} ${org}/${name}`
    );
    if (!a.gcpWifProvider) out.push('   gh variable set DAWNFIX_GCP_WIF_PROVIDER --body "<the provider name setup-wif.sh prints>"');
  }
  out.push(
    `${n++}. Secrets (gh asks for the value and does not echo it):`,
    "   gh secret set ANTHROPIC_API_KEY",
    "   gh secret set DAWNFIX_ENTERPRISE_KEY   # optional, Enterprise only: turns on hosted reporting",
    `${n++}. Commit both files on a branch, open a pull request and merge it.`,
    `${n++}. gh workflow run dawnfix.yml -f dry_run=true   # prints exactly what would leave your account`,
    "   gh workflow run dawnfix.yml -f baseline=true  # records what is already failing, opens nothing",
    `${n++}. npx dawnfix doctor`
  );
  return out.join("\n") + "\n";
}
function fail(io2, msg) {
  io2.stderr(`dawnfix init: ${msg}
`);
  return 2;
}
async function init(argv, io2) {
  let v;
  try {
    ({ values: v } = parseArgs3({ args: argv, options: OPTIONS, allowPositionals: false, strict: true }));
  } catch (e) {
    return fail(io2, `${e.message}

${INIT_HELP}`);
  }
  if (v.help) {
    io2.stdout(INIT_HELP);
    return 0;
  }
  const repo = detectRepo(v.dir || io2.cwd);
  if (!repo) return fail(io2, "not inside a git repository: run it at the root of the repo Dawnfix should watch");
  if (!repo.slug) io2.stderr("dawnfix init: no GitHub remote named origin; the next steps say OWNER/REPO\n");
  const ask = io2.isTTY && !v.yes ? createInterface({ input: io2.stdin, output: io2.stdoutStream }) : null;
  const prompt = async (text, dflt) => {
    if (!ask) return dflt;
    const answer = (await ask.question(`${text}${dflt ? ` [${dflt}]` : ""}: `)).trim();
    return answer || dflt;
  };
  try {
    const guess = detectCommands(repo.root);
    const a = { ref: v.ref || MAJOR_REF, enterprise: Boolean(v.enterprise), schedule: v.schedule || "17 * * * *" };
    a.cloud = v.cloud || (v["gcp-project"] ? "gcp" : await prompt("Where are the logs: aws or gcp", "aws"));
    if (!["aws", "gcp"].includes(a.cloud)) return fail(io2, `--cloud must be aws or gcp, not ${q(a.cloud)}`);
    a.logGroups = [];
    if (a.cloud === "aws") {
      a.awsRegion = v["aws-region"] || await prompt("AWS region of the log groups", "us-east-1");
      a.logGroups = v["log-group"] || (await prompt("CloudWatch log groups to watch, comma separated (blank: alarms only)", "")).split(",").map((s) => s.trim()).filter(Boolean);
      a.alarms = v["no-alarms"] ? false : v.alarms ?? (a.logGroups.length === 0 ? true : (await prompt("Also report alarms in ALARM (y/n)", "y")).startsWith("y"));
      a.awsRoleArn = v["aws-role-arn"] || await prompt("Read-only role ARN, if it exists (blank: set it up next)", "");
    } else {
      a.gcpProject = v["gcp-project"] || await prompt("GCP project id", "");
      if (!a.gcpProject) return fail(io2, "--gcp-project is required with --cloud gcp");
      a.gcpWifProvider = v["gcp-wif-provider"] || await prompt("Workload identity provider, if it exists (blank: set it up next)", "");
    }
    a.autonomy = v.autonomy || await prompt("Autonomy: diagnose (issues only), plan or draft-pr", "diagnose");
    if (!["diagnose", "plan", "draft-pr"].includes(a.autonomy)) return fail(io2, `--autonomy must be diagnose, plan or draft-pr, not ${q(a.autonomy)}`);
    const fixes = a.autonomy !== "diagnose";
    a.testCommand = v["test-command"] ?? (fixes ? await prompt("Test command the fix agent may run", guess.test) : guess.test);
    a.installCommand = v["install-command"] ?? (fixes ? await prompt("Install command before the fix agent runs", guess.install) : "");
    if (a.autonomy === "draft-pr" && !a.testCommand) {
      io2.stderr("dawnfix init: draft-pr without a test command can only open issues (no failing test, no PR)\n");
    }
    if (a.awsRoleArn && !/^arn:aws[a-z-]*:iam::\d{1,12}:role\/[\w+=,.@/-]+$/.test(a.awsRoleArn)) {
      return fail(io2, `--aws-role-arn ${q(a.awsRoleArn)} is not an IAM role ARN`);
    }
    if (!/^(v\d+(\.\d+){0,2}|[0-9a-f]{40})$/.test(a.ref)) return fail(io2, `--ref must be a release tag (v0, v0.3.0) or a commit SHA, not ${q(a.ref)}`);
    const config = renderConfig(a);
    const errors = validate(config_schema_default, (0, import_yaml2.parse)(config));
    if (errors.length) return fail(io2, `these settings make an invalid .dawnfix.yml:
${errors.map((e) => `  ${e.path}: ${e.message}`).join("\n")}`);
    const files = [
      [".dawnfix.yml", config],
      [".github/workflows/dawnfix.yml", renderCaller(a)]
    ];
    let exists;
    try {
      exists = files.filter(([p]) => checkTarget(repo.root, p).exists).map(([p]) => p);
    } catch (e) {
      if (e instanceof UnsafePath) return fail(io2, e.message);
      throw e;
    }
    io2.stdout(`Dawnfix ${VERSION} in ${repo.slug || repo.root}. ${v["dry-run"] ? "Dry run: nothing is written." : "These files will be written:"}
`);
    for (const [p, text] of files) {
      io2.stdout(`
--- ${p}${exists.includes(p) ? " (exists; replaced only with --force)" : ""}
${text}`);
    }
    io2.stdout("---\n\n");
    if (v["dry-run"]) {
      io2.stdout(nextSteps(a, repo));
      return 0;
    }
    if (exists.length && !v.force) return fail(io2, `${exists.join(" and ")} exist already; re-run with --force to replace, or run npx dawnfix doctor`);
    if (!v.yes) {
      if (!ask) return fail(io2, "not a terminal: re-run with --yes to write these files (or --dry-run to only show them)");
      const ok = (await ask.question("Write these files? [y/N]: ")).trim().toLowerCase();
      if (!ok.startsWith("y")) {
        io2.stdout("Nothing written.\n");
        return 1;
      }
    }
    for (const [p, text] of files) {
      try {
        safeWrite(repo.root, p, text, { overwrite: Boolean(v.force) });
      } catch (e) {
        if (e instanceof UnsafePath) return fail(io2, e.message);
        throw e;
      }
      io2.stdout(`wrote ${p}
`);
    }
    io2.stdout(`
${nextSteps(a, repo)}`);
    return 0;
  } finally {
    ask?.close();
  }
}

// src/cli.mjs
var HELP2 = `Dawnfix ${VERSION}: the AI SRE that runs in your own GitHub Actions.
Source available under FSL-1.1-ALv2. https://dawnfix.dev

Usage: npx dawnfix <command> [options]

Commands:
  init        Set Dawnfix up in this repo: .dawnfix.yml and a 15-line workflow that calls
              dawnfix/dawnfix/.github/workflows/dawnfix.yml. Shows both before writing.
  doctor      Check the setup: the config, the pinned workflow, secret and variable
              names, Free or Enterprise.
  flare ...   Dawnfix Flare: read-only audit of Cloudflare accounts and Workers
              (npx dawnfix flare --help).

Options:
  -v, --version   Print the version
  -h, --help      This help (and <command> --help)

The Python tools (dawnfix, logbill, parity, sweeper, leastpriv, receipt, fleet) are the
PyPI package of the same version: pipx install dawnfix==${VERSION}
`;
async function run(argv, io2) {
  const [cmd, ...rest] = argv;
  if (!cmd || cmd === "-h" || cmd === "--help" || cmd === "help") {
    io2.stdout(HELP2);
    return cmd ? 0 : 2;
  }
  if (cmd === "-v" || cmd === "--version" || cmd === "version") {
    io2.stdout(`${VERSION}
`);
    return 0;
  }
  if (cmd === "init") return init(rest, io2);
  if (cmd === "doctor") return doctor(rest, io2);
  if (cmd === "flare") return main(rest, io2);
  io2.stderr(`dawnfix: unknown command ${JSON.stringify(cmd)}

${HELP2}`);
  return 2;
}
var io = {
  env: process.env,
  fetch: globalThis.fetch,
  stdout: (s) => process.stdout.write(s),
  stderr: (s) => process.stderr.write(s),
  now: () => /* @__PURE__ */ new Date(),
  isTTY: Boolean(process.stdin.isTTY && process.stdout.isTTY),
  ...process.stdout.columns ? { columns: process.stdout.columns } : {},
  cwd: process.cwd(),
  stdin: process.stdin,
  stdoutStream: process.stdout
};
run(process.argv.slice(2), io).then(
  (code) => {
    process.exitCode = code;
  },
  (e) => {
    process.stderr.write(`dawnfix: ${e instanceof Error ? e.message : String(e)}
`);
    process.exitCode = 2;
  }
);
export {
  HELP2 as HELP,
  run
};
