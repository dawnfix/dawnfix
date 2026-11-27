// A small JSON Schema validator: exactly the keywords core/schema/config.schema.json uses.
// Returns a list of { path, message }; empty means valid.

const KEYWORDS = new Set([
  '$schema', '$id', '$ref', '$defs', 'title', 'description', 'default', 'type', 'const', 'enum',
  'required', 'properties', 'additionalProperties', 'items', 'minItems', 'minProperties',
  'maxProperties', 'minLength', 'maxLength', 'pattern', 'exclusiveMinimum', 'maximum', 'anyOf', 'not',
]);

function typeOf(v) {
  if (v === null) return 'null';
  if (Array.isArray(v)) return 'array';
  if (typeof v === 'number') return Number.isInteger(v) ? 'integer' : 'number';
  return typeof v;
}

function typeOk(want, v) {
  const t = typeOf(v);
  return t === want || (want === 'number' && t === 'integer');
}

const show = (v) => JSON.stringify(v);

export function validate(schema, value, root = schema, path = '') {
  for (const k of Object.keys(schema)) {
    if (!KEYWORDS.has(k)) throw new Error(`schema keyword ${k} is not supported by this validator`);
  }
  const errs = [];
  const at = path || '/';
  if (schema.$ref) {
    const name = schema.$ref.replace(/^#\/\$defs\//, '');
    errs.push(...validate(root.$defs[name], value, root, path));
  }
  if (schema.type && !typeOk(schema.type, value)) {
    errs.push({ path: at, message: `expected ${schema.type}, got ${typeOf(value)}` });
    return errs;
  }
  if ('const' in schema && value !== schema.const) errs.push({ path: at, message: `must be ${show(schema.const)}` });
  if (schema.enum && !schema.enum.includes(value)) {
    errs.push({ path: at, message: `must be one of ${schema.enum.join(', ')}, got ${show(value)}` });
  }
  if (schema.not && validate(schema.not, value, root, path).length === 0) {
    errs.push({ path: at, message: schema.description || 'not allowed' });
  }
  if (typeOf(value) === 'string') {
    if (schema.minLength !== undefined && value.length < schema.minLength) errs.push({ path: at, message: 'must not be empty' });
    if (schema.maxLength !== undefined && value.length > schema.maxLength) {
      errs.push({ path: at, message: `at most ${schema.maxLength} characters` });
    }
    if (schema.pattern && !new RegExp(schema.pattern, 'u').test(value)) {
      errs.push({ path: at, message: `${show(value.slice(0, 60))} is not valid${schema.description ? `: ${schema.description}` : ''}` });
    }
  }
  if (typeof value === 'number') {
    if (schema.exclusiveMinimum !== undefined && !(value > schema.exclusiveMinimum)) {
      errs.push({ path: at, message: `must be greater than ${schema.exclusiveMinimum}` });
    }
    if (schema.maximum !== undefined && value > schema.maximum) errs.push({ path: at, message: `at most ${schema.maximum}` });
  }
  if (typeOf(value) === 'object') {
    const keys = Object.keys(value);
    for (const r of schema.required || []) {
      if (!(r in value)) errs.push({ path: at, message: `missing required key ${r}` });
    }
    if (schema.minProperties !== undefined && keys.length < schema.minProperties) {
      errs.push({ path: at, message: `needs at least ${schema.minProperties} key(s)` });
    }
    if (schema.maxProperties !== undefined && keys.length > schema.maxProperties) {
      errs.push({ path: at, message: `at most ${schema.maxProperties} key(s), got ${keys.join(', ')}` });
    }
    for (const k of keys) {
      if (schema.properties && k in schema.properties) {
        errs.push(...validate(schema.properties[k], value[k], root, `${path}/${k}`));
      } else if (schema.additionalProperties === false) {
        const allowed = Object.keys(schema.properties || {}).join(', ');
        errs.push({ path: at, message: `unknown key ${k} (allowed: ${allowed})` });
      }
    }
  }
  if (Array.isArray(value)) {
    if (schema.minItems !== undefined && value.length < schema.minItems) {
      errs.push({ path: at, message: schema.minItems === 1 ? 'must not be empty' : `needs at least ${schema.minItems} items` });
    }
    if (schema.items) value.forEach((v, i) => errs.push(...validate(schema.items, v, root, `${path}/${i}`)));
  }
  if (schema.anyOf) {
    const tries = schema.anyOf.map((s) => validate(s, value, root, path));
    if (!tries.some((t) => t.length === 0)) {
      // One branch of the right type: its own errors say more than "no form matched".
      const typed = schema.anyOf.map((s, i) => [s, tries[i]]).filter(([s]) => !s.type || typeOk(s.type, value));
      if (typed.length === 1 && typed[0][0].type) errs.push(...typed[0][1]);
      else errs.push({ path: at, message: schema.description || 'does not match any allowed form' });
    }
  }
  return errs;
}
