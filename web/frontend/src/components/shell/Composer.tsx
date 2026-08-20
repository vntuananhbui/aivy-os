"use client";

import { useEffect, useId, useMemo, useReducer, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { createPortal } from "react-dom";
import {
  AlertCircle,
  ArrowUp,
  ChevronDown,
  ClipboardPaste,
  Gauge,
  Globe2,
  KeyRound,
  Link2,
  Loader2,
  Microscope,
  Minus,
  Plus,
  Redo2,
  Square,
  Table2,
  Undo2,
  X,
} from "lucide-react";

import { useSettings } from "@/components/settings/SettingsProvider";
import RunOverridesPopover from "@/components/settings/RunOverridesPopover";
import ComposerPlusMenu from "@/components/shell/ComposerPlusMenu";
import ComposerSourcesPopover, { DATA_SOURCES, SourceIcon, faviconOf } from "@/components/shell/ComposerSourcesPopover";
import SharePointConnectModal from "@/components/shell/SharePointConnectModal";
import JiraConnectModal from "@/components/shell/JiraConnectModal";
import { useConnectedSources } from "@/components/shell/ConnectedSourcesProvider";
import Select from "@/components/ui/Select";
import {
  parseDelimitedTable,
  validateSchemaDrafts,
  type RelationDraft,
  type SchemaSnapshot,
  type TableDraft,
} from "@/lib/schemaDraft";

export interface SubmitOpts {
  entities?: string[];
  attrs?: string[];
  tableLabel?: string;
  primaryKey?: string[];
  rowLabel?: string;
  tables?: {
    table_id: string;
    table_label?: string;
    entities?: string[];
    attrs: string[];
    primary_key?: string[];
    row_label?: string;
  }[];
  relations?: {
    from_table: string;
    to_table: string;
    foreign_key: string[];
    target_columns?: string[];
    kind: "one_to_many" | "many_to_many";
    label?: string;
  }[];
  /** true = deep research (orchestrator + sub-agents), false = plain chat. */
  deepResearch?: boolean;
  /** false = don't query the web provider at all this run (e.g. SharePoint-only). */
  webSearchEnabled?: boolean;
}

interface Props {
  onSubmit: (query: string, opts: SubmitOpts) => void;
  /** When set, submitting while `running` steers the live run instead of being ignored. */
  onSteer?: (text: string) => void;
  /** When set, a stop button interrupts the live run while `running`. */
  onStop?: () => void;
  stopping?: boolean;
  running?: boolean;
  /** "hero" = large landing composer, "bar" = compact in-conversation bar */
  variant?: "hero" | "bar";
  placeholder?: string;
  autoFocus?: boolean;
  focusRequest?: number;
  /** Deep-research toggle: uncontrolled by default, or pass both props to control it. */
  deepResearch?: boolean;
  onDeepResearchChange?: (value: boolean) => void;
}

// "kind" drives the chip color in the menu (and, once composed, in the sent
// message bubble — see ChatView.tsx's CommandChip): "agent" = a dedicated
// command-agent (quickchat/commands/catalog.py) dispatched server-side,
// blue. "local" = a composer-only action (/schema) that never reaches the
// backend, no color — plain text. A future "skill" kind (purple, --accent)
// is reserved but not implemented yet.
type CommandKind = "local" | "agent";
const COMMANDS: { cmd: string; hint: string; kind: CommandKind }[] = [
  { cmd: "/schema", hint: "Pin rows (entities) and cols (attributes)", kind: "local" },
];

const csv = (s: string) => {
  const items = s.split(",").map((x) => x.trim()).filter(Boolean);
  return items.length ? items : undefined;
};

type DrawPoint = {
  x: number;
  y: number;
};

type DrawPreview = DrawPoint & {
  width: number;
  height: number;
  dragWidth: number;
  dragHeight: number;
  rows: number;
  cols: number;
};

const DRAW_CELL_W = 108;
const DRAW_CELL_H = 34;
// Sentinel activeDraftId meaning "drawing a brand-new table" — distinct from
// null (which means "nothing explicitly chosen yet, default to the first
// table"), so the "+ Table" button actually reveals the draw area instead of
// immediately snapping back to the existing table.
const NEW_TABLE_ID = "__new_table__";
const MIN_DRAW_SIZE = 26;
const HISTORY_LIMIT = 60;

type SchemaHistoryState = {
  past: SchemaSnapshot[];
  present: SchemaSnapshot;
  future: SchemaSnapshot[];
  mergeKey: string | null;
};

type SchemaHistoryAction =
  | { type: "commit"; update: (snapshot: SchemaSnapshot) => SchemaSnapshot; mergeKey?: string }
  | { type: "break" }
  | { type: "undo" }
  | { type: "redo" };

const EMPTY_SCHEMA: SchemaSnapshot = { tableDrafts: [], relationDrafts: [] };

function schemaHistoryReducer(state: SchemaHistoryState, action: SchemaHistoryAction): SchemaHistoryState {
  if (action.type === "commit") {
    const next = action.update(state.present);
    if (next === state.present) return state;
    if (action.mergeKey && action.mergeKey === state.mergeKey) {
      return { ...state, present: next, future: [] };
    }
    return {
      past: [...state.past, state.present].slice(-HISTORY_LIMIT),
      present: next,
      future: [],
      mergeKey: action.mergeKey ?? null,
    };
  }
  if (action.type === "break") return state.mergeKey ? { ...state, mergeKey: null } : state;
  if (action.type === "undo") {
    const previous = state.past.at(-1);
    if (!previous) return state;
    return {
      past: state.past.slice(0, -1),
      present: previous,
      future: [state.present, ...state.future],
      mergeKey: null,
    };
  }
  const next = state.future[0];
  if (!next) return state;
  return {
    past: [...state.past, state.present].slice(-HISTORY_LIMIT),
    present: next,
    future: state.future.slice(1),
    mergeKey: null,
  };
}

const clamp = (n: number, min: number, max: number) => Math.max(min, Math.min(max, n));

const cleanList = (items: string[]) => {
  const cleaned = items.map((x) => x.trim()).filter(Boolean);
  return cleaned.length ? cleaned : undefined;
};

const countLabel = (count: number, singular: string, plural = `${singular}s`) => `${count} ${count === 1 ? singular : plural}`;

const makeDraft = (rows: number, dataCols: number, id: string): TableDraft => ({
  id,
  entityName: "",
  primaryKey: "ID",
  rows: Array.from({ length: rows }, () => ""),
  columns: Array.from({ length: dataCols }, (_, i) => `字段 ${i + 1}`),
});

const tableSlug = (label: string, index: number) => {
  const slug = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return `${slug || "table"}_${index + 1}`;
};

const draftLabel = (draft: TableDraft, index: number) => draft.entityName.trim() || `Table ${index + 1}`;

const draftPrimaryKey = (draft: TableDraft) => {
  const label = draft.entityName.trim();
  return draft.primaryKey.trim() || (label ? `${label} ID` : "ID");
};

const draftAttrs = (draft: TableDraft, index: number) => [
  draftPrimaryKey(draft),
  ...(cleanList(draft.columns) ?? [`字段 ${index + 1}`]),
];

export default function Composer({
  onSubmit,
  onSteer,
  onStop,
  stopping = false,
  running = false,
  variant = "bar",
  placeholder,
  autoFocus = false,
  focusRequest = 0,
  deepResearch: deepResearchProp,
  onDeepResearchChange,
}: Props) {
  const [text, setText] = useState("");
  const [deepResearchState, setDeepResearchState] = useState(false);
  const deepResearch = deepResearchProp ?? deepResearchState;
  const setDeepResearch = (next: boolean) => {
    setDeepResearchState(next);
    onDeepResearchChange?.(next);
  };
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const [showSourcesPopover, setShowSourcesPopover] = useState(false);
  // Demo-only connectors (Google Search/SharePoint/Outlook/...); "web link"
  // is handled separately via the real trusted/excluded domain overrides
  // below. Google Search is connected by default; at least one must stay on
  // (enforced in ComposerSourcesPopover, which disables the last toggle).
  // Shared across every mounted `<Composer>` (Landing/Conversation/ChatView)
  // via context — see ConnectedSourcesProvider.tsx for why this can't be
  // local state.
  const {
    connectedSources, toggleConnectedSource,
    showSharePointModal, openSharePointModal, closeSharePointModal, markSharePointConnected,
    showJiraModal, openJiraModal, closeJiraModal, markJiraConnected,
  } = useConnectedSources();
  const [focused, setFocused] = useState(false);
  const [showSchema, setShowSchema] = useState(false);
  const [showOverrides, setShowOverrides] = useState(false);
  const [entities, setEntities] = useState("");
  const [attrs, setAttrs] = useState("");
  const [schemaHistory, dispatchSchema] = useReducer(schemaHistoryReducer, {
    past: [],
    present: EMPTY_SCHEMA,
    future: [],
    mergeKey: null,
  });
  const [activeDraftId, setActiveDraftId] = useState<string | null>(null);
  const [dragStart, setDragStart] = useState<DrawPoint | null>(null);
  const [dragNow, setDragNow] = useState<DrawPoint | null>(null);
  const [showPaste, setShowPaste] = useState(false);
  const [pasteEntityName, setPasteEntityName] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [sel, setSel] = useState(0);
  const [menuDismissed, setMenuDismissed] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);
  const schemaIdPrefix = useId().replace(/[^a-z0-9]/gi, "");
  const schemaIdCounter = useRef(0);
  const { overrides, setOverrides, clearOverrides, settings } = useSettings();
  const trustedDomains = overrides.trusted_domains ?? [];
  const excludedDomains = overrides.excluded_domains ?? [];
  // Deep research's own pill only surfaces what's unique to it (trusted/
  // excluded web domains) — connected sources (Google, SharePoint, Slack...)
  // already get their own chips below, always visible regardless of the
  // Deep research toggle, so repeating them here would duplicate the UI.
  const attachedSourceIcons: { id: string; label: string; domain?: string }[] =
    trustedDomains.length || excludedDomains.length ? [{ id: "web", label: "Web link" }] : [];
  // Every connected source gets its own icon chip near the composer,
  // independent of whether Deep research is on.
  const connectedConnectorSources = connectedSources
    .filter((id) => id !== "web")
    .map((id) => DATA_SOURCES.find((s) => s.id === id))
    .filter((s): s is (typeof DATA_SOURCES)[number] => Boolean(s));
  const { tableDrafts, relationDrafts } = schemaHistory.present;
  const schemaValidation = useMemo(
    () => validateSchemaDrafts(tableDrafts, relationDrafts),
    [relationDrafts, tableDrafts],
  );
  const schemaInvalid = tableDrafts.length > 0 && !schemaValidation.valid;
  const pasteResult = useMemo(() => parseDelimitedTable(pasteText), [pasteText]);
  const issueFor = (key: string) => schemaValidation.byKey[key]?.[0];
  const tablesWithIssues = new Set(
    schemaValidation.issues.flatMap((issue) => issue.key.startsWith("table:") ? [issue.key.split(":")[1]] : []),
  );

  const overridesActive = overrides.effort != null || overrides.max_time != null || overrides.thinking != null;
  // Pinned schema follows the *content*, not the panel visibility — collapsing
  // the panel must not silently drop what the user typed.
  const resolvedActiveDraftId = activeDraftId === NEW_TABLE_ID
    ? null
    : activeDraftId && tableDrafts.some((draft) => draft.id === activeDraftId)
      ? activeDraftId
      : tableDrafts[0]?.id ?? null;
  const activeDraft = tableDrafts.find((draft) => draft.id === resolvedActiveDraftId) ?? null;
  const hasDraftTables = tableDrafts.length > 0;
  const resolvedEntityName = activeDraft?.entityName.trim() ?? "";
  const resolvedPrimaryKey = activeDraft?.primaryKey.trim() || (resolvedEntityName ? `${resolvedEntityName} ID` : "ID");
  const draftRows = activeDraft ? cleanList(activeDraft.rows) : undefined;
  const draftDataCols = activeDraft ? cleanList(activeDraft.columns) : undefined;
  const draftCols = activeDraft ? [resolvedPrimaryKey, ...(draftDataCols ?? [])] : undefined;
  const tableMetas = tableDrafts.map((draft, index) => {
    const label = draftLabel(draft, index);
    const primaryKey = draftPrimaryKey(draft);
    return {
      draft,
      tableId: tableSlug(label, index),
      label,
      primaryKey,
      attrs: draftAttrs(draft, index),
    };
  });
  const tableMetaByDraftId = new Map(tableMetas.map((meta) => [meta.draft.id, meta]));
  const schemaTables = hasDraftTables
    ? tableMetas.map((meta) => ({
      table_id: meta.tableId,
      table_label: meta.label,
      entities: cleanList(meta.draft.rows),
      attrs: meta.attrs,
      primary_key: [meta.primaryKey],
      row_label: meta.label,
    }))
    : undefined;
  const schemaRelations = hasDraftTables
    ? relationDrafts.flatMap((rel) => {
      const from = tableMetaByDraftId.get(rel.fromDraftId);
      const to = tableMetaByDraftId.get(rel.toDraftId);
      if (!from || !to || !rel.fromColumn.trim()) return [];
      return [{
        from_table: from.tableId,
        to_table: to.tableId,
        foreign_key: [rel.fromColumn.trim()],
        target_columns: [to.primaryKey],
        kind: rel.kind,
        label: rel.label.trim() || undefined,
      }];
    })
    : undefined;
  const pinnedRows = hasDraftTables ? draftRows : csv(entities);
  const pinnedCols = hasDraftTables ? draftCols : csv(attrs);
  const schemaPinned = hasDraftTables || !!(pinnedRows || pinnedCols);
  const visibleColCount = activeDraft ? (pinnedCols?.length ?? activeDraft.columns.length + 1) : (pinnedCols?.length ?? 0);
  const overrideChip = [
    overrides.thinking === false ? "no thinking" : null,
    overrides.effort,
    overrides.max_time != null ? `${overrides.max_time}s` : null,
  ].filter(Boolean).join(" · ");

  const hero = variant === "hero";
  // Backend-dispatched quickchat commands (Settings -> Models -> Commands,
  // quickchat/commands/catalog.py) alongside the local-only "/schema" command
  // above — same menu, same Tab/click selection. hint = the bound agent's
  // catalog description, falling back to the raw agent_type if settings
  // hasn't loaded / the catalog entry went stale.
  const dynamicCommands = useMemo(() => {
    const bound = settings?.models.commands ?? {};
    const catalog = settings?.models.command_catalog ?? {};
    return Object.entries(bound).map(([name, agentType]) => ({
      cmd: `/${name}`,
      hint: catalog[agentType] ?? agentType,
      kind: "agent" as const,
    }));
  }, [settings]);
  const allCommands = useMemo(() => [...COMMANDS, ...dynamicCommands], [dynamicCommands]);
  const boundCommandNames = settings?.models.commands ?? {};
  const slashTyping = /^\/[a-zA-Z0-9_-]*$/.test(text);
  const matches = slashTyping ? allCommands.filter((c) => c.cmd.toLowerCase().startsWith(text.toLowerCase())) : [];
  // Live "/name" highlight WHILE TYPING, inside the composer box itself —
  // distinct from the dropdown above (matches) and from the chip a sent
  // message gets in ChatView.tsx. A plain <textarea> can't color part of its
  // own text, so this renders the same text into an aria-hidden overlay div
  // stacked behind an otherwise-identical but text-transparent textarea (see
  // the `relative` wrapper around both, below) — only the leading "/name"
  // needs coloring, so overlay + real caret line up without a full syntax
  // highlighter.
  const leadingCommandMatch = /^\/(\S+)(?:([ \t][\s\S]*))?$/.exec(text);
  const highlightedInput = leadingCommandMatch && leadingCommandMatch[1] in boundCommandNames
    ? (
      <>
        <span className="text-agent-ink">/{leadingCommandMatch[1]}</span>
        {leadingCommandMatch[2] ?? ""}
      </>
    )
    : text;
  const menuOpen = matches.length > 0 && focused && !menuDismissed;

  const commitSchema = (update: (snapshot: SchemaSnapshot) => SchemaSnapshot, mergeKey?: string) => {
    dispatchSchema({ type: "commit", update, mergeKey });
  };
  const breakSchemaMerge = () => dispatchSchema({ type: "break" });
  const nextSchemaId = (kind: "draft" | "rel") => {
    schemaIdCounter.current += 1;
    return `${kind}_${schemaIdPrefix}_${schemaIdCounter.current}`;
  };

  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

  useEffect(() => {
    if (focusRequest > 0) ref.current?.focus();
  }, [focusRequest]);

  // autosize
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, hero ? 200 : 160)}px`;
  }, [text, hero]);

  const choose = (cmd: string) => {
    if (cmd === "/schema") {
      setShowSchema((v) => !v);
      setText("");
    } else {
      // A backend quickchat command (dynamicCommands above): drop it into the
      // composer with a trailing space so the user keeps typing the rest of
      // the message — quickchat/session.py::_parse_command splits it back
      // into command + rest server-side. Not submitted here; Enter still
      // does that once the user finishes the sentence.
      setText(`${cmd} `);
    }
    setMenuDismissed(true);
    ref.current?.focus();
  };

  const submit = () => {
    const body = text.trim();
    if (!body) return;
    // Local slash commands (COMMANDS above, e.g. "/schema") are picked from
    // the dropdown menu and handled entirely by `choose()` while it's open —
    // onKey intercepts Enter/Tab for that case before it ever reaches here
    // (see menuOpen branch below). Anything else starting with "/" (a
    // quickchat backend command like "/meeting ...", or just a literal "/"
    // in the user's question) is a normal chat message from this layer's
    // perspective — quickchat/session.py::_parse_command decides server-side
    // whether the leading word is a registered command.
    if (running) {
      // Mid-run: steer the live orchestrator rather than queue a new search.
      if (!onSteer) return;
      onSteer(body);
      setText("");
      return;
    }
    if (hasDraftTables && !schemaValidation.valid) {
      setShowSchema(true);
      return;
    }
    onSubmit(body, {
      entities: pinnedRows,
      attrs: pinnedCols,
      tableLabel: hasDraftTables ? resolvedEntityName || undefined : undefined,
      primaryKey: hasDraftTables ? [resolvedPrimaryKey] : undefined,
      rowLabel: hasDraftTables ? resolvedEntityName || undefined : undefined,
      tables: schemaTables,
      relations: schemaRelations,
      deepResearch,
      webSearchEnabled: connectedSources.includes("google"),
    });
    setText("");
  };

  const clearSchema = () => {
    setEntities("");
    setAttrs("");
    if (hasDraftTables || relationDrafts.length > 0) {
      commitSchema(() => EMPTY_SCHEMA);
    }
    setActiveDraftId(null);
    setShowPaste(false);
    setPasteEntityName("");
    setPasteText("");
    setShowSchema(false);
  };

  // Snap to the visible grid (background-size DRAW_CELL_W×DRAW_CELL_H) so the
  // drag preview's cell edges line up with the drawn grid lines instead of
  // floating at whatever raw pixel the pointer landed on.
  const snapToGrid = (v: number, cell: number) => Math.round(v / cell) * cell;

  const drawPoint = (e: PointerEvent<HTMLDivElement>): DrawPoint => {
    const rect = e.currentTarget.getBoundingClientRect();
    return {
      x: snapToGrid(clamp(e.clientX - rect.left, 0, rect.width), DRAW_CELL_W),
      y: snapToGrid(clamp(e.clientY - rect.top, 0, rect.height), DRAW_CELL_H),
    };
  };

  const drawPreview = (a: DrawPoint, b: DrawPoint): DrawPreview => {
    const dragWidth = Math.abs(b.x - a.x);
    const dragHeight = Math.abs(b.y - a.y);
    const cols = clamp(Math.round(dragWidth / DRAW_CELL_W), 2, 8);
    const rows = clamp(Math.round(dragHeight / DRAW_CELL_H) - 1, 1, 12);
    const width = cols * DRAW_CELL_W;
    const height = (rows + 1) * DRAW_CELL_H;
    return {
      x: b.x >= a.x ? a.x : Math.max(0, a.x - width),
      y: b.y >= a.y ? a.y : Math.max(0, a.y - height),
      width,
      height,
      dragWidth,
      dragHeight,
      rows,
      cols,
    };
  };

  const preview = dragStart && dragNow ? drawPreview(dragStart, dragNow) : null;

  const startDrawing = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const point = drawPoint(e);
    setDragStart(point);
    setDragNow(point);
  };

  const moveDrawing = (e: PointerEvent<HTMLDivElement>) => {
    if (!dragStart) return;
    setDragNow(drawPoint(e));
  };

  const finishDrawing = () => {
    if (preview && preview.dragWidth >= MIN_DRAW_SIZE && preview.dragHeight >= MIN_DRAW_SIZE) {
      const draft = makeDraft(preview.rows, Math.max(1, preview.cols - 1), nextSchemaId("draft"));
      commitSchema((snapshot) => ({ ...snapshot, tableDrafts: [...snapshot.tableDrafts, draft] }));
      setActiveDraftId(draft.id);
    }
    setDragStart(null);
    setDragNow(null);
  };

  const updateDraft = (patch: Partial<TableDraft>, mergeKey?: string) => {
    if (!resolvedActiveDraftId) return;
    commitSchema((snapshot) => ({
      ...snapshot,
      tableDrafts: snapshot.tableDrafts.map((draft) => draft.id === resolvedActiveDraftId ? { ...draft, ...patch } : draft),
    }), mergeKey);
  };

  const removeDraft = (id: string) => {
    commitSchema((snapshot) => ({
      tableDrafts: snapshot.tableDrafts.filter((draft) => draft.id !== id),
      relationDrafts: snapshot.relationDrafts.filter((draft) => draft.fromDraftId !== id && draft.toDraftId !== id),
    }));
    if (activeDraftId === id) setActiveDraftId(tableDrafts.find((draft) => draft.id !== id)?.id ?? null);
  };

  const addRelation = () => {
    if (tableDrafts.length < 2) return;
    const from = tableDrafts[1] ?? tableDrafts[0];
    const to = tableDrafts[0];
    const fromColumn = cleanList(from.columns)?.[0] ?? draftPrimaryKey(from);
    const relationId = nextSchemaId("rel");
    commitSchema((snapshot) => ({
      ...snapshot,
      relationDrafts: [
        ...snapshot.relationDrafts,
        {
          id: relationId,
          fromDraftId: from.id,
          fromColumn,
          toDraftId: to.id,
          kind: "one_to_many",
          label: "",
        },
      ],
    }));
  };

  const updateRelation = (id: string, patch: Partial<RelationDraft>, mergeKey?: string) => {
    commitSchema((snapshot) => ({
      ...snapshot,
      relationDrafts: snapshot.relationDrafts.map((draft) => draft.id === id ? { ...draft, ...patch } : draft),
    }), mergeKey);
  };

  const removeRelation = (id: string) => {
    commitSchema((snapshot) => ({
      ...snapshot,
      relationDrafts: snapshot.relationDrafts.filter((draft) => draft.id !== id),
    }));
  };

  const updateDraftRow = (index: number, value: string) => {
    if (!activeDraft) return;
    const rows = [...activeDraft.rows];
    rows[index] = value;
    updateDraft({ rows }, `table:${activeDraft.id}:row:${index}`);
  };

  const updateDraftColumn = (index: number, value: string) => {
    if (!activeDraft) return;
    const previous = activeDraft.columns[index];
    commitSchema((snapshot) => ({
      tableDrafts: snapshot.tableDrafts.map((draft) => {
        if (draft.id !== activeDraft.id) return draft;
        const columns = [...draft.columns];
        columns[index] = value;
        return { ...draft, columns };
      }),
      relationDrafts: snapshot.relationDrafts.map((relation) => (
        relation.fromDraftId === activeDraft.id && relation.fromColumn === previous
          ? { ...relation, fromColumn: value }
          : relation
      )),
    }), `table:${activeDraft.id}:column:${index}`);
  };

  const updatePrimaryKey = (value: string) => {
    if (!activeDraft) return;
    const previous = activeDraft.primaryKey;
    commitSchema((snapshot) => ({
      tableDrafts: snapshot.tableDrafts.map((draft) => draft.id === activeDraft.id ? { ...draft, primaryKey: value } : draft),
      relationDrafts: snapshot.relationDrafts.map((relation) => (
        relation.fromDraftId === activeDraft.id && relation.fromColumn === previous
          ? { ...relation, fromColumn: value }
          : relation
      )),
    }), `table:${activeDraft.id}:primary`);
  };

  const addDraftRow = () => {
    if (!activeDraft) return;
    updateDraft({ rows: [...activeDraft.rows, ""] });
  };

  const addDraftColumn = () => {
    if (!activeDraft) return;
    updateDraft({ columns: [...activeDraft.columns, `字段 ${activeDraft.columns.length + 1}`] });
  };

  const removeDraftColumn = (index: number) => {
    if (!activeDraft || activeDraft.columns.length <= 1) return;
    const removed = activeDraft.columns[index];
    const columns = activeDraft.columns.filter((_, i) => i !== index);
    const replacement = columns[0] ?? activeDraft.primaryKey;
    commitSchema((snapshot) => ({
      tableDrafts: snapshot.tableDrafts.map((draft) => draft.id === activeDraft.id ? { ...draft, columns } : draft),
      relationDrafts: snapshot.relationDrafts.map((relation) => (
        relation.fromDraftId === activeDraft.id && relation.fromColumn === removed
          ? { ...relation, fromColumn: replacement }
          : relation
      )),
    }));
  };

  const resizeRows = (count: number) => {
    if (!activeDraft) return;
    const nextCount = clamp(count, 1, 50);
    const rows = Array.from({ length: nextCount }, (_, index) => activeDraft.rows[index] ?? "");
    updateDraft({ rows });
  };

  const resizeColumns = (count: number) => {
    if (!activeDraft) return;
    const nextCount = clamp(count, 1, 20);
    const columns = Array.from(
      { length: nextCount },
      (_, index) => activeDraft.columns[index] ?? `字段 ${index + 1}`,
    );
    const validColumns = new Set([activeDraft.primaryKey, ...columns]);
    commitSchema((snapshot) => ({
      tableDrafts: snapshot.tableDrafts.map((draft) => draft.id === activeDraft.id ? { ...draft, columns } : draft),
      relationDrafts: snapshot.relationDrafts.map((relation) => (
        relation.fromDraftId === activeDraft.id && !validColumns.has(relation.fromColumn)
          ? { ...relation, fromColumn: columns[0] ?? activeDraft.primaryKey }
          : relation
      )),
    }));
  };

  const importPastedTable = () => {
    if (!pasteResult.ok || !pasteEntityName.trim()) return;
    const draft: TableDraft = {
      id: nextSchemaId("draft"),
      entityName: pasteEntityName.trim(),
      primaryKey: pasteResult.table.headers[0],
      rows: pasteResult.table.rows.map((row) => row[0]).filter(Boolean),
      columns: pasteResult.table.headers.slice(1),
    };
    commitSchema((snapshot) => ({ ...snapshot, tableDrafts: [...snapshot.tableDrafts, draft] }));
    setActiveDraftId(draft.id);
    setPasteEntityName("");
    setPasteText("");
    setShowPaste(false);
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing || e.nativeEvent.keyCode === 229) return;
    if (menuOpen) {
      if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => (s + 1) % matches.length); return; }
      if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => (s - 1 + matches.length) % matches.length); return; }
      if (e.key === "Tab" || e.key === "Enter") { e.preventDefault(); choose(matches[sel].cmd); return; }
      if (e.key === "Escape") { setMenuDismissed(true); return; }
    }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  };

  return (
    <div className="relative w-full">
      <form
        onSubmit={(e) => { e.preventDefault(); submit(); }}
        className={`surface flex flex-col gap-2.5 transition-shadow focus-within:border-line-strong ${
          hero ? "rounded-2xl px-4 py-3.5 shadow-[0_2px_18px_rgba(21,34,56,0.06)]" : "rounded-2xl px-3.5 py-3"
        }`}
      >
        {/* Row 1 — the prompt. A leading bound "/command" needs live-typing
            color, which a plain textarea can't do on its own text — only
            while that's true do we stack an aria-hidden highlight div behind
            a text-transparent textarea (same box, so the real caret still
            lines up with the colored text showing through); otherwise it's
            a completely normal opaque textarea, no overlay/scroll-sync cost. */}
        <div className="relative w-full">
          {highlightedInput !== text && (
            <div
              ref={highlightRef}
              aria-hidden
              className={`pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words leading-relaxed ${
                hero ? "text-[16px]" : "text-[15px]"
              }`}
            >
              {highlightedInput}
            </div>
          )}
          <textarea
            ref={ref}
            rows={1}
            value={text}
            onChange={(e) => { setText(e.target.value); setSel(0); setMenuDismissed(false); }}
            onKeyDown={onKey}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onScroll={(e) => {
              if (highlightRef.current) highlightRef.current.scrollTop = e.currentTarget.scrollTop;
            }}
            spellCheck={false}
            placeholder={
              running
                ? onSteer
                  ? "Searching… press Enter to steer the live run"
                  : "Searching… type your next question"
                : placeholder ?? (deepResearch ? "Ask anything — deep research is on…" : "Ask anything…")
            }
            className={`min-w-0 w-full resize-none bg-transparent leading-relaxed caret-accent outline-none placeholder:text-ink-faint disabled:opacity-50 ${
              highlightedInput !== text ? "text-transparent" : "text-ink"
            } ${hero ? "text-[16px]" : "text-[15px]"}`}
          />
        </div>

        {/* Row 2 — controls */}
        <div className="flex flex-wrap items-center gap-1.5">
          <div className="relative shrink-0">
            <button
              type="button"
              onClick={() => setShowPlusMenu((v) => !v)}
              title="Add a mode"
              aria-label="Open the mode menu"
              aria-expanded={showPlusMenu}
              className={`flex items-center gap-1 rounded-full border p-1.5 transition-colors ${
                showPlusMenu ? "border-line-strong bg-surface-2 text-ink-dim" : "border-line text-ink-faint hover:bg-surface-2 hover:text-ink-dim"
              }`}
            >
              <Plus size={hero ? 17 : 15} className={`transition-transform ${showPlusMenu ? "rotate-45" : ""}`} />
            </button>
            {showPlusMenu && (
              <ComposerPlusMenu
                direction={hero ? "down" : "up"}
                deepResearch={deepResearch}
                onSelectDeepResearch={() => setDeepResearch(!deepResearch)}
                connectedSources={connectedSources}
                onToggleConnector={toggleConnectedSource}
                onClose={() => setShowPlusMenu(false)}
              />
            )}
          </div>

          {deepResearch && (
            <div className="relative shrink-0">
              {/* Split pill — highlighted when on. Left part opens the options
                  popover (chevron signals it); the trailing × turns it off. */}
              <div className="flex items-center rounded-full border border-accent/40 bg-clay text-accent-ink">
                <button
                  type="button"
                  onClick={() => setShowSourcesPopover((v) => !v)}
                  title="Configure deep research — sources, skills, table"
                  aria-label="Configure deep research"
                  aria-expanded={showSourcesPopover}
                  className="flex items-center gap-1.5 rounded-l-full py-1.5 pl-2.5 pr-1.5 text-[12.5px] font-medium transition-opacity hover:opacity-80"
                >
                  <Microscope size={hero ? 15 : 14} />
                  <span>Deep research</span>
                  {attachedSourceIcons.length > 0 && (
                    <span className="flex items-center -space-x-1.5 pl-0.5">
                      {attachedSourceIcons.slice(0, 4).map((s) =>
                        s.domain ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img key={s.id} src={faviconOf(s.domain)} alt={s.label} title={s.label} width={16} height={16}
                            className="rounded-full border border-paper bg-paper" />
                        ) : (
                          <span key={s.id} title={s.label}
                            className="grid h-4 w-4 place-items-center rounded-full border border-paper bg-surface-2">
                            <Globe2 size={10} className="text-ink-dim" />
                          </span>
                        ),
                      )}
                      {attachedSourceIcons.length > 4 && (
                        <span className="pl-1.5 text-[10.5px] tabular-nums">+{attachedSourceIcons.length - 4}</span>
                      )}
                    </span>
                  )}
                  <ChevronDown size={13} className={`transition-transform ${showSourcesPopover ? "rotate-180" : ""}`} />
                </button>
                <button
                  type="button"
                  onClick={() => { setDeepResearch(false); setShowSourcesPopover(false); }}
                  title="Turn off deep research"
                  aria-label="Turn off deep research"
                  className="flex items-center rounded-r-full border-l border-accent/20 py-1.5 pl-1.5 pr-2.5 transition-opacity hover:opacity-70"
                >
                  <X size={13} />
                </button>
              </div>
              {showSourcesPopover && (
                <ComposerSourcesPopover
                  direction={hero ? "down" : "up"}
                  trustedDomains={trustedDomains}
                  excludedDomains={excludedDomains}
                  onTrustedDomainsChange={(values) => setOverrides({ ...overrides, trusted_domains: values.length ? values : undefined })}
                  onExcludedDomainsChange={(values) => setOverrides({ ...overrides, excluded_domains: values.length ? values : undefined })}
                  onOpenSchema={() => setShowSchema(true)}
                  schemaSummary={schemaPinned
                    ? (hasDraftTables
                        ? countLabel(tableDrafts.length, "table")
                        : `${countLabel(pinnedRows?.length ?? 0, "row")} × ${countLabel(pinnedCols?.length ?? 0, "col")}`)
                    : undefined}
                  onClose={() => setShowSourcesPopover(false)}
                />
              )}
            </div>
          )}

          {connectedConnectorSources.map((source) => (
            <div key={source.id} className="group/conn relative shrink-0">
              <button
                type="button"
                onClick={() => {
                  if (source.id === "sharepoint") openSharePointModal();
                  if (source.id === "jira") openJiraModal();
                }}
                title={
                  source.id === "sharepoint" ? "Manage the SharePoint connection"
                    : source.id === "jira" ? "Manage the Jira connection"
                    : source.label
                }
                aria-label={
                  source.id === "sharepoint" ? "Manage the SharePoint connection"
                    : source.id === "jira" ? "Manage the Jira connection"
                    : source.label
                }
                className="flex h-8 w-8 items-center justify-center rounded-full border border-accent/40 bg-clay transition-opacity hover:opacity-80"
              >
                <SourceIcon source={source} size={hero ? 18 : 16} />
              </button>
              <button
                type="button"
                onClick={() => toggleConnectedSource(source.id)}
                title={`Disconnect ${source.label}`}
                aria-label={`Disconnect ${source.label}`}
                className="absolute -right-1 -top-1 flex h-4 w-4 scale-90 items-center justify-center rounded-full border border-paper bg-ink-dim text-paper opacity-0 transition-all group-hover/conn:scale-100 group-hover/conn:opacity-100 hover:bg-err"
              >
                <X size={10} />
              </button>
            </div>
          ))}

          {deepResearch && schemaPinned && !showSchema && (
            <span className={`flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-[11px] ${schemaInvalid ? "bg-err/10 text-err" : "bg-surface-2/60 text-ink-dim"}`}>
              {schemaInvalid && <AlertCircle size={11} />}
              <Table2 size={11} />
              {hasDraftTables
                ? countLabel(tableDrafts.length, "table")
                : `${countLabel(pinnedRows?.length ?? 0, "row")} × ${countLabel(pinnedCols?.length ?? 0, "col")}`}
              <button type="button" aria-label="Clear pinned schema" onClick={clearSchema}
                className="rounded-sm transition-opacity hover:opacity-70">
                <X size={11} />
              </button>
            </span>
          )}

          {/* Right cluster */}
          <div className="ml-auto flex items-center gap-1.5">
            {overridesActive && (
              <span className={`flex shrink-0 items-center gap-1 rounded-full bg-clay px-2 py-1 text-[11px] text-accent-ink ${overrides.effort === "max" ? "max-effort-chip" : ""}`}>
                {overrideChip}
                <button type="button" aria-label="Clear run overrides" onClick={clearOverrides}
                  className="rounded-sm transition-opacity hover:opacity-70">
                  <X size={11} />
                </button>
              </span>
            )}
            <div className="relative shrink-0">
              <button
                type="button"
                onClick={() => setShowOverrides((v) => !v)}
                title={deepResearch ? "This run only — effort & time" : "This run only — effort"}
                aria-label="Run overrides"
                className={`flex items-center gap-1 rounded-full border p-1.5 transition-colors ${overrides.effort === "max" ? "max-effort-control" : ""} ${
                  showOverrides || overridesActive ? "border-accent/40 bg-clay text-accent-ink" : "border-line text-ink-faint hover:bg-surface-2 hover:text-ink-dim"
                }`}
              >
                <Gauge size={hero ? 17 : 15} />
              </button>
              {showOverrides && (
                <RunOverridesPopover
                  direction={hero ? "down" : "up"}
                  align="right"
                  onClose={() => setShowOverrides(false)}
                  simple={!deepResearch}
                />
              )}
            </div>
            {running && onStop && (
              <button
                type="button"
                onClick={onStop}
                disabled={stopping}
                aria-label={stopping ? "Stopping the run" : "Stop the run"}
                title={stopping ? "Stopping the run" : "Stop the run"}
                className="shrink-0 rounded-full border border-err/40 p-2 text-err transition-colors hover:bg-err/10 disabled:cursor-wait disabled:opacity-60"
              >
                {stopping ? (
                  <Loader2 className="animate-spin" size={hero ? 16 : 14} />
                ) : (
                  <Square size={hero ? 16 : 14} fill="currentColor" />
                )}
              </button>
            )}
            <button
              type="submit"
              disabled={!text.trim() || (running && !onSteer)}
              aria-label={running && onSteer ? "Steer the live run" : "Send"}
              title={running && onSteer ? "Steer the live run" : undefined}
              className="shrink-0 rounded-full bg-accent p-2 text-white transition-opacity hover:opacity-90 disabled:opacity-25"
            >
              <ArrowUp size={hero ? 18 : 16} />
            </button>
          </div>
        </div>
      </form>

      {/* Table-schema editor — centered modal overlay, portaled to body so no
          transformed/overflow ancestor clips or mis-anchors the fixed layer. */}
      {deepResearch && showSchema && typeof document !== "undefined" && createPortal(
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:items-center" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm" onClick={() => setShowSchema(false)} />
          <div className="rise-in surface relative z-10 my-auto max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-2xl p-4 text-left shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[14px] font-medium text-ink">Pin table schema</span>
              <button type="button" onClick={() => setShowSchema(false)} aria-label="Close"
                className="rounded-md p-1 text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink">
                <X size={16} />
              </button>
            </div>
          <div className="mb-2 flex items-start gap-2">
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
              {tableDrafts.map((draft, i) => {
                const label = draft.entityName.trim() || `Table ${i + 1}`;
                const active = draft.id === resolvedActiveDraftId;
                const invalid = tablesWithIssues.has(draft.id);
                return (
                  <div
                    key={draft.id}
                    className={`flex items-center rounded-lg border text-[12px] transition-colors ${
                      invalid
                        ? "border-err/40 bg-err/5 text-err"
                        : active
                        ? "border-line-strong bg-clay text-accent-ink"
                        : "border-line bg-surface text-ink-dim hover:bg-surface-2"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => setActiveDraftId(draft.id)}
                      className="flex min-w-0 items-center gap-1 px-2 py-1"
                    >
                      <Table2 size={12} />
                      <span className="max-w-24 truncate">{label}</span>
                      {invalid && <AlertCircle size={11} />}
                    </button>
                    {tableDrafts.length > 1 && (
                      <button
                        type="button"
                        aria-label="Remove table"
                        onClick={() => removeDraft(draft.id)}
                        className="mr-1 rounded-sm p-0.5 text-ink-faint hover:text-ink-dim"
                      >
                        <X size={11} />
                      </button>
                    )}
                  </div>
                );
              })}
              {hasDraftTables && (
                <button
                  type="button"
                  onClick={() => setActiveDraftId(NEW_TABLE_ID)}
                  className={`flex items-center gap-1 rounded-lg border px-2 py-1 text-[12px] transition-colors ${
                    activeDraftId === NEW_TABLE_ID
                      ? "border-line-strong bg-clay text-accent-ink"
                      : "border-line bg-surface text-ink-faint hover:bg-surface-2 hover:text-ink-dim"
                  }`}
                >
                  <Plus size={12} />
                  Table
                </button>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-0.5">
              <button type="button" onClick={() => setShowPaste((value) => !value)}
                aria-label="Paste CSV or TSV" title="Paste CSV or TSV"
                className={`grid h-7 w-7 place-items-center rounded-md transition-colors ${showPaste ? "bg-clay text-accent-ink" : "text-ink-faint hover:bg-surface-2 hover:text-ink"}`}>
                <ClipboardPaste size={14} />
              </button>
              <button type="button" onClick={() => dispatchSchema({ type: "undo" })}
                disabled={schemaHistory.past.length === 0} aria-label="Undo schema change" title="Undo"
                className="grid h-7 w-7 place-items-center rounded-md text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink disabled:cursor-not-allowed disabled:opacity-25">
                <Undo2 size={14} />
              </button>
              <button type="button" onClick={() => dispatchSchema({ type: "redo" })}
                disabled={schemaHistory.future.length === 0} aria-label="Redo schema change" title="Redo"
                className="grid h-7 w-7 place-items-center rounded-md text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink disabled:cursor-not-allowed disabled:opacity-25">
                <Redo2 size={14} />
              </button>
            </div>
          </div>

          {showPaste && (
            <div className="surface mb-2 overflow-hidden rounded-xl">
              <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
                <label className="flex min-w-[190px] flex-1 items-center gap-2 text-[12px]">
                  <span className="shrink-0 text-ink-faint">Entity</span>
                  <input value={pasteEntityName} onChange={(event) => setPasteEntityName(event.target.value)}
                    placeholder="Customers" autoFocus spellCheck={false}
                    className="min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-ink-faint" />
                </label>
                {pasteResult.ok && (
                  <span className="text-[11px] text-ink-faint">
                    {pasteResult.table.rows.length} rows · {pasteResult.table.headers.length} columns · {pasteResult.table.delimiter === "\t" ? "TSV" : "CSV"}
                  </span>
                )}
              </div>
              <textarea value={pasteText} onChange={(event) => setPasteText(event.target.value)} rows={4}
                placeholder={'customer_id,name,region\nC-001,Acme,APAC'} spellCheck={false}
                className="block w-full resize-y bg-transparent px-3 py-2 font-mono text-[12px] leading-5 text-ink outline-none placeholder:text-ink-faint" />
              <div className="flex items-center gap-2 border-t border-line px-3 py-2">
                {pasteText && !pasteResult.ok && <span role="alert" className="min-w-0 flex-1 text-[11px] text-err">{pasteResult.error}</span>}
                {!pasteText && <span className="min-w-0 flex-1 text-[11px] text-ink-faint">CSV / TSV</span>}
                <button type="button" onClick={() => { setShowPaste(false); setPasteText(""); setPasteEntityName(""); }}
                  className="rounded-md px-2 py-1 text-[12px] text-ink-faint hover:bg-surface-2 hover:text-ink">Cancel</button>
                <button type="button" onClick={importPastedTable} disabled={!pasteResult.ok || !pasteEntityName.trim()}
                  className="rounded-md bg-accent px-2.5 py-1 text-[12px] font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30">Create table</button>
              </div>
            </div>
          )}

          {activeDraft ? (
            <div className="surface overflow-hidden rounded-xl">
              <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2 text-[13px]">
                <label title={issueFor(`table:${activeDraft.id}:entity`)} className={`flex min-w-[180px] flex-1 items-center gap-2 rounded-md px-2 py-1 ${issueFor(`table:${activeDraft.id}:entity`) ? "bg-err/5 text-err ring-1 ring-err/35" : ""}`}>
                  <span className="shrink-0 text-ink-faint">Entity</span>
                  <input
                    autoFocus
                    value={activeDraft.entityName}
                    onChange={(e) => updateDraft({ entityName: e.target.value }, `table:${activeDraft.id}:entity`)}
                    onBlur={breakSchemaMerge}
                    placeholder="客户"
                    aria-invalid={!!issueFor(`table:${activeDraft.id}:entity`)}
                    spellCheck={false}
                    className="min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-ink-faint"
                  />
                </label>
                <label title={issueFor(`table:${activeDraft.id}:primary`)} className={`flex min-w-[170px] flex-1 items-center gap-2 rounded-md px-2 py-1 ${issueFor(`table:${activeDraft.id}:primary`) ? "bg-err/5 text-err ring-1 ring-err/35" : ""}`}>
                  <KeyRound size={13} className="shrink-0 text-accent-ink" />
                  <input
                    value={activeDraft.primaryKey}
                    onChange={(e) => updatePrimaryKey(e.target.value)}
                    onBlur={breakSchemaMerge}
                    placeholder={resolvedEntityName ? `${resolvedEntityName} ID` : "ID"}
                    aria-label="Primary key column"
                    aria-invalid={!!issueFor(`table:${activeDraft.id}:primary`)}
                    spellCheck={false}
                    className="min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-ink-faint"
                  />
                </label>
                <div className="flex items-center gap-2 text-[11px] text-ink-faint">
                  <span className="flex items-center rounded-md border border-line bg-surface-2/50">
                    <span className="px-1.5">Rows</span>
                    <button type="button" onClick={() => resizeRows(activeDraft.rows.length - 1)} disabled={activeDraft.rows.length <= 1}
                      aria-label="Remove last row" title="Remove last row" className="grid h-6 w-6 place-items-center border-l border-line hover:bg-clay hover:text-ink disabled:opacity-25"><Minus size={11} /></button>
                    <span className="min-w-6 border-l border-line px-1 text-center font-mono text-ink-dim">{activeDraft.rows.length}</span>
                    <button type="button" onClick={() => resizeRows(activeDraft.rows.length + 1)}
                      aria-label="Add row" title="Add row" className="grid h-6 w-6 place-items-center border-l border-line hover:bg-clay hover:text-ink"><Plus size={11} /></button>
                  </span>
                  <span className="flex items-center rounded-md border border-line bg-surface-2/50">
                    <span className="px-1.5">Cols</span>
                    <button type="button" onClick={() => resizeColumns(activeDraft.columns.length - 1)} disabled={activeDraft.columns.length <= 1}
                      aria-label="Remove last column" title="Remove last column" className="grid h-6 w-6 place-items-center border-l border-line hover:bg-clay hover:text-ink disabled:opacity-25"><Minus size={11} /></button>
                    <span className="min-w-6 border-l border-line px-1 text-center font-mono text-ink-dim">{activeDraft.columns.length + 1}</span>
                    <button type="button" onClick={() => resizeColumns(activeDraft.columns.length + 1)}
                      aria-label="Add column" title="Add column" className="grid h-6 w-6 place-items-center border-l border-line hover:bg-clay hover:text-ink"><Plus size={11} /></button>
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => removeDraft(activeDraft.id)}
                  className="rounded-lg px-2 py-1 text-[12px] text-ink-faint transition-colors hover:bg-clay hover:text-ink-dim"
                >
                  Redraw
                </button>
              </div>
              {(issueFor(`table:${activeDraft.id}:entity`) || issueFor(`table:${activeDraft.id}:primary`)) && (
                <div role="alert" className="flex flex-wrap gap-x-3 gap-y-1 border-b border-err/20 bg-err/5 px-3 py-1.5 text-[11px] text-err">
                  {issueFor(`table:${activeDraft.id}:entity`) && <span>{issueFor(`table:${activeDraft.id}:entity`)}</span>}
                  {issueFor(`table:${activeDraft.id}:primary`) && <span>{issueFor(`table:${activeDraft.id}:primary`)}</span>}
                </div>
              )}
              <div className="overflow-x-auto">
                <table className="min-w-full table-fixed border-collapse text-[13px]">
                  <thead>
                    <tr className="border-b border-line bg-surface-2/60">
                      <th className="w-36 border-r border-line px-2 py-1.5 text-left font-medium text-ink">
                        <div className="flex items-center gap-1.5">
                          <KeyRound size={13} className="shrink-0 text-accent-ink" />
                          <span className="truncate">{resolvedPrimaryKey}</span>
                        </div>
                      </th>
                      {activeDraft.columns.map((col, i) => (
                        <th key={i} title={issueFor(`table:${activeDraft.id}:column:${i}`)} className={`w-36 border-r px-2 py-1.5 text-left font-medium ${issueFor(`table:${activeDraft.id}:column:${i}`) ? "border-err/40 bg-err/5" : "border-line"}`}>
                          <div className="flex items-center gap-1">
                            <input
                              value={col}
                              onChange={(e) => updateDraftColumn(i, e.target.value)}
                              onBlur={breakSchemaMerge}
                              aria-invalid={!!issueFor(`table:${activeDraft.id}:column:${i}`)}
                              onKeyDown={(e) => {
                                if (e.key === "Tab" && !e.shiftKey && i === activeDraft.columns.length - 1) {
                                  addDraftColumn();
                                }
                              }}
                              spellCheck={false}
                              className="min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-ink-faint"
                            />
                            <button
                              type="button"
                              aria-label="Remove column"
                              onClick={() => removeDraftColumn(i)}
                              disabled={activeDraft.columns.length <= 1}
                              className="rounded p-0.5 text-ink-faint transition-colors hover:bg-clay hover:text-ink-dim disabled:opacity-20"
                            >
                              <X size={11} />
                            </button>
                          </div>
                        </th>
                      ))}
                      <th className="w-10 px-1 py-1.5">
                        <button
                          type="button"
                          aria-label="Add column"
                          onClick={addDraftColumn}
                          className="rounded-md p-1 text-ink-faint transition-colors hover:bg-clay hover:text-ink-dim"
                        >
                          <Plus size={13} />
                        </button>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeDraft.rows.map((row, rowIndex) => (
                      <tr key={rowIndex} className="border-b border-line last:border-b-0">
                        <td title={issueFor(`table:${activeDraft.id}:row:${rowIndex}`)} className={`border-r px-2 py-1.5 ${issueFor(`table:${activeDraft.id}:row:${rowIndex}`) ? "border-err/40 bg-err/5" : "border-line"}`}>
                          <input
                            value={row}
                            onChange={(e) => updateDraftRow(rowIndex, e.target.value)}
                            onBlur={breakSchemaMerge}
                            aria-invalid={!!issueFor(`table:${activeDraft.id}:row:${rowIndex}`)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && rowIndex === activeDraft.rows.length - 1) {
                                e.preventDefault();
                                addDraftRow();
                              }
                            }}
                            placeholder={`实体 ${rowIndex + 1}`}
                            spellCheck={false}
                            className="w-full bg-transparent font-medium text-ink outline-none placeholder:text-ink-faint"
                          />
                        </td>
                        {activeDraft.columns.map((_, colIndex) => (
                          <td key={colIndex} className="border-r border-line px-2 py-1.5 text-ink-faint">
                            —
                          </td>
                        ))}
                        <td />
                      </tr>
                    ))}
                    <tr>
                      <td colSpan={activeDraft.columns.length + 2} className="px-2 py-1.5">
                        <button
                          type="button"
                          onClick={addDraftRow}
                          className="flex items-center gap-1 rounded-md px-1.5 py-1 text-[12px] text-ink-faint transition-colors hover:bg-clay hover:text-ink-dim"
                        >
                          <Plus size={12} />
                          Row
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <>
              <div
                onPointerDown={startDrawing}
                onPointerMove={moveDrawing}
                onPointerUp={finishDrawing}
                onPointerCancel={finishDrawing}
                className="surface relative h-44 cursor-crosshair overflow-hidden rounded-xl bg-surface-2/45"
                style={{
                  touchAction: "none",
                  backgroundImage: "linear-gradient(to right, var(--line) 1px, transparent 1px), linear-gradient(to bottom, var(--line) 1px, transparent 1px)",
                  backgroundSize: `${DRAW_CELL_W}px ${DRAW_CELL_H}px`,
                }}
              >
                <div className="pointer-events-none absolute left-3 top-2 flex items-center gap-2 text-[12px] text-ink-faint">
                  <Table2 size={14} />
                  <span>Drag table area</span>
                </div>
                {preview && (
                  <div
                    className="pointer-events-none absolute grid overflow-hidden rounded-lg border border-accent bg-accent/10 shadow-sm"
                    style={{
                      left: preview.x,
                      top: preview.y,
                      width: preview.width,
                      height: preview.height,
                      gridTemplateColumns: `repeat(${preview.cols}, minmax(0, 1fr))`,
                      gridTemplateRows: `repeat(${preview.rows + 1}, minmax(0, 1fr))`,
                    }}
                  >
                    {Array.from({ length: preview.cols * (preview.rows + 1) }).map((_, i) => (
                      <div key={i} className="border-b border-r border-accent/35" />
                    ))}
                    <div className="absolute right-1 top-1 whitespace-nowrap rounded bg-accent px-1.5 py-0.5 text-[11px] text-white">
                      {preview.rows} rows · {preview.cols} cols
                    </div>
                  </div>
                )}
              </div>
              {!hasDraftTables && (
                <div className="grid grid-cols-1 gap-2 text-[13px] sm:grid-cols-2">
                  <label className="surface flex items-center gap-2 rounded-xl px-3 py-2 focus-within:border-line-strong">
                    <span className="shrink-0 text-ink-faint">Rows</span>
                    <input
                      autoFocus
                      value={entities}
                      onChange={(e) => setEntities(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); submit(); } }}
                      placeholder="Tesla, BYD, NIO"
                      spellCheck={false}
                      className="w-full bg-transparent text-ink outline-none placeholder:text-ink-faint"
                    />
                  </label>
                  <label className="surface flex items-center gap-2 rounded-xl px-3 py-2 focus-within:border-line-strong">
                    <span className="shrink-0 text-ink-faint">Cols</span>
                    <input
                      value={attrs}
                      onChange={(e) => setAttrs(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); submit(); } }}
                      placeholder="price, range, 0-100 km/h"
                      spellCheck={false}
                      className="w-full bg-transparent text-ink outline-none placeholder:text-ink-faint"
                    />
                  </label>
                </div>
              )}
            </>
          )}

          {hasDraftTables && (
            <div className="surface mt-2 rounded-xl px-3 py-2">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[12px] font-medium text-ink-dim">Relations</span>
                <button
                  type="button"
                  onClick={addRelation}
                  disabled={tableDrafts.length < 2}
                  className="flex items-center gap-1 rounded-md px-1.5 py-1 text-[12px] text-ink-faint transition-colors hover:bg-clay hover:text-ink-dim disabled:opacity-30"
                >
                  <Plus size={12} />
                  Relation
                </button>
              </div>
              {relationDrafts.length > 0 ? (
                <div className="space-y-1.5">
                  {relationDrafts.map((rel) => {
                    const fromMeta = tableMetaByDraftId.get(rel.fromDraftId) ?? tableMetas[0];
                    const toMeta = tableMetaByDraftId.get(rel.toDraftId) ?? tableMetas[0];
                    const fromAttrs = fromMeta?.attrs ?? [];
                    const relationIssue = issueFor(`relation:${rel.id}`);
                    return (
                      <div key={rel.id} className={`rounded-lg p-1.5 text-[12px] ${relationIssue ? "bg-err/5 ring-1 ring-err/30" : "bg-surface-2/35"}`}>
                        <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
                          <Select
                            value={rel.fromDraftId}
                            onChange={(value) => {
                              const nextFrom = tableMetaByDraftId.get(value);
                              const nextTarget = value === rel.toDraftId
                                ? tableMetas.find((meta) => meta.draft.id !== value)?.draft.id ?? rel.toDraftId
                                : rel.toDraftId;
                              updateRelation(rel.id, {
                                fromDraftId: value,
                                fromColumn: nextFrom?.attrs.find((attr) => attr !== nextFrom.primaryKey) ?? nextFrom?.primaryKey ?? "",
                                toDraftId: nextTarget,
                              });
                            }}
                            options={tableMetas.map((meta) => ({ value: meta.draft.id, label: meta.label }))}
                            ariaLabel="Source table"
                            className="w-full"
                            size="sm"
                          />
                          <Select
                            value={fromAttrs.includes(rel.fromColumn) ? rel.fromColumn : fromAttrs[0] ?? ""}
                            onChange={(value) => updateRelation(rel.id, { fromColumn: value })}
                            options={fromAttrs.map((attr) => ({ value: attr, label: attr }))}
                            ariaLabel="Foreign key column"
                            className="w-full"
                            size="sm"
                          />
                          <Select
                            value={rel.toDraftId}
                            onChange={(value) => updateRelation(rel.id, { toDraftId: value })}
                            options={tableMetas.map((meta) => ({
                              value: meta.draft.id,
                              label: `${meta.label}.${meta.primaryKey}`,
                              disabled: meta.draft.id === rel.fromDraftId,
                            }))}
                            ariaLabel="Target table and primary key"
                            className="w-full"
                            size="sm"
                          />
                          <div className="flex items-center gap-1">
                            <Select
                              value={rel.kind}
                              onChange={(value) => updateRelation(rel.id, { kind: value as RelationDraft["kind"] })}
                              options={[
                                { value: "one_to_many", label: "1:N" },
                                { value: "many_to_many", label: "N:N" },
                              ]}
                              ariaLabel="Relation type"
                              className="w-full"
                              size="sm"
                            />
                            <button
                              type="button"
                              aria-label="Remove relation"
                              onClick={() => removeRelation(rel.id)}
                              className="rounded-md p-1 text-ink-faint transition-colors hover:bg-clay hover:text-ink-dim"
                            >
                              <X size={12} />
                            </button>
                          </div>
                          <input
                            value={rel.label}
                            onChange={(e) => updateRelation(rel.id, { label: e.target.value }, `relation:${rel.id}:label`)}
                            onBlur={breakSchemaMerge}
                            placeholder={`${fromMeta?.label ?? "From"} -> ${toMeta?.label ?? "To"}`}
                            spellCheck={false}
                            className="rounded-md border border-line bg-surface px-2 py-1 text-ink outline-none placeholder:text-ink-faint sm:col-span-4"
                          />
                        </div>
                        {relationIssue && (
                          <div role="alert" className="mt-1 flex items-center gap-1 text-[11px] text-err"><AlertCircle size={11} />{relationIssue}</div>
                        )}
                        {rel.kind === "many_to_many" && !relationIssue && (
                          <div className="mt-1 flex items-center gap-1 text-[11px] text-warn">
                            <Link2 size={11} />
                            Junction semantics: {fromMeta?.label}.{rel.fromColumn} ↔ {toMeta?.label}.{toMeta?.primaryKey}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-md border border-dashed border-line px-2 py-2 text-[12px] text-ink-faint">
                  Add a relation after creating at least two tables.
                </div>
              )}
            </div>
          )}

          {hasDraftTables && !schemaValidation.valid && (
            <div role="alert" className="mt-2 flex items-start gap-2 rounded-lg border border-err/30 bg-err/5 px-3 py-2 text-[12px] text-err">
              <AlertCircle className="mt-0.5 shrink-0" size={14} />
              <span>{schemaValidation.issues.length} schema {schemaValidation.issues.length === 1 ? "issue" : "issues"} must be fixed before search.</span>
            </div>
          )}

          <div className="mt-1.5 flex items-baseline justify-between px-1 text-[11.5px] text-ink-faint">
            <span>{hasDraftTables
              ? `${countLabel(tableDrafts.length, "table")} · ${countLabel(relationDrafts.length, "relation")} · ${countLabel(pinnedRows?.length ?? 0, "primary value")} × ${countLabel(visibleColCount, "column")} in current table`
              : "Optional — pin the table's rows and columns (comma-separated). Leave empty and the orchestrator designs the schema itself."}</span>
            {schemaPinned && (
              <button type="button" onClick={clearSchema} className="shrink-0 pl-3 text-ink-faint transition-colors hover:text-ink-dim">
                Clear
              </button>
            )}
          </div>
          </div>
        </div>,
        document.body,
      )}

      {/* slash menu */}
      {menuOpen && (
        // Opens upward (bottom-full), not downward: in ChatView/Conversation
        // the composer sits near the bottom of the viewport, so a menu
        // growing downward would render past the visible area and get
        // clipped by the surrounding overflow-hidden containers — upward
        // always has the message history above to render into instead.
        <div className="surface absolute inset-x-0 bottom-full z-20 mb-2 max-h-[min(320px,60vh)] overflow-y-auto rounded-xl shadow-xl">
          {matches.map((c, i) => (
            <button
              key={c.cmd}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => choose(c.cmd)}
              onMouseEnter={() => setSel(i)}
              className={`flex w-full items-baseline gap-3 px-4 py-2 text-left text-[13px] ${
                i === sel ? (c.kind === "agent" ? "bg-agent/10" : "bg-clay/50") : ""
              }`}
            >
              <span className={`flex w-20 shrink-0 items-center gap-1.5 font-mono ${
                c.kind === "agent" ? "text-agent-ink" : i === sel ? "text-accent-ink" : "text-ink-dim"
              }`}>
                {c.kind === "agent" && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-agent" />}
                {c.cmd}
              </span>
              <span className="truncate text-ink-faint">{c.hint}</span>
            </button>
          ))}
        </div>
      )}

      {showSharePointModal && (
        <SharePointConnectModal
          onConnected={() => {
            markSharePointConnected();
            closeSharePointModal();
          }}
          onClose={closeSharePointModal}
        />
      )}

      {showJiraModal && (
        <JiraConnectModal
          onConnected={() => {
            markJiraConnected();
            closeJiraModal();
          }}
          onClose={closeJiraModal}
        />
      )}
    </div>
  );
}
