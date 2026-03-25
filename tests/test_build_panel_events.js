/**
 * Frontend Build Panel Event Test
 * =================================
 * This test loads the captured WebSocket events (from the backend test)
 * and simulates EXACTLY what the frontend does with them:
 *
 * 1. use-app-events.tsx handleEvent → creates/updates Redux messages
 * 2. agent-controller.tsx → filters messages with actions
 * 3. agent-build.tsx → reads currentActionData, computes buildingTitle & searchBrowserProps
 *
 * Usage:
 *   cd agents-backend
 *   npx tsx tests/test_build_panel_events.ts
 *   (or: node --loader ts-node/esm tests/test_build_panel_events.ts)
 *   (or simply: node tests/test_build_panel_events.ts)
 *
 * This file has NO dependencies — it uses plain JS with the logic extracted
 * from the frontend React components.
 */

const fs = require('fs');
const path = require('path');

// =============================================================================
// Frontend TOOL enum (from frontend/src/typings/agent.ts)
// =============================================================================
const TOOL = {
    SEQUENTIAL_THINKING: 'sequential_thinking',
    MESSAGE_USER: 'message_user',
    RETURN_CONTROL_TO_USER: 'return_control_to_user',
    COMPLETE: 'complete',
    WEB_SEARCH: 'web_search',
    WEB_BATCH_SEARCH: 'web_batch_search',
    IMAGE_SEARCH: 'image_search',
    VISIT: 'web_visit',
    TAVILY_SEARCH: 'tavily_search_results_json',
    CRAWL: 'crawl',
    TODO_WRITE: 'TodoWrite',
    TODO_READ: 'TodoRead',
    FULLSTACK_PROJECT_INIT: 'fullstack_project_init',
};

// =============================================================================
// Frontend parseJson (from frontend/src/lib/utils.ts)
// =============================================================================
function parseJson(jsonString) {
    try {
        return JSON.parse(jsonString);
    } catch {
        return null;
    }
}

// =============================================================================
// Load captured events from backend test
// =============================================================================
const capturedFile = path.join(__dirname, 'captured_websocket_events.json');

if (!fs.existsSync(capturedFile)) {
    console.error('❌ No captured events file found!');
    console.error('   Run the backend test first: python -m tests.test_websocket_transform');
    process.exit(1);
}

const capturedData = JSON.parse(fs.readFileSync(capturedFile, 'utf-8'));
const events = capturedData.websocket_events;

console.log('='.repeat(80));
console.log('Frontend Build Panel Event Test');
console.log('='.repeat(80));
console.log(`\nLoaded ${events.length} captured WebSocket events\n`);

// =============================================================================
// Simulate use-app-events.tsx handleEvent
// =============================================================================
// This replicates the TOOL_CALL and TOOL_RESULT cases from handleEvent

const messages = [];  // Redux message store

for (const event of events) {
    const data = event;  // The Socket.IO "chat_event" payload

    if (data.type === 'tool_call') {
        // --- TOOL_CALL handler (use-app-events.tsx lines 507-534) ---
        const message = {
            id: data.content.tool_call_id,
            role: 'assistant',
            action: {
                type: data.content.tool_name,  // "web_search"
                data: {
                    ...data.content,
                    // agentContext would be added here
                },
            },
            timestamp: Date.now(),
        };

        messages.push(message);
        console.log(`[TOOL_CALL] Created message with action.type = "${message.action.type}"`);
        console.log(`  tool_input: ${JSON.stringify(message.action.data.tool_input)}`);

    } else if (data.type === 'tool_result') {
        // --- TOOL_RESULT handler (use-app-events.tsx lines 588-622) ---

        // Skip certain tool types
        if (
            data.content.tool_name === TOOL.SEQUENTIAL_THINKING ||
            data.content.tool_name === TOOL.MESSAGE_USER ||
            data.content.tool_name === TOOL.RETURN_CONTROL_TO_USER
        ) {
            console.log(`[TOOL_RESULT] Skipped (${data.content.tool_name})`);
            continue;
        }

        // Find matching tool call (search backwards)
        let lastToolCallMessageIndex = -1;
        for (let i = messages.length - 1; i >= 0; i--) {
            if (
                messages[i].action?.type === data.content.tool_name &&
                !messages[i].action?.data?.isResult
            ) {
                lastToolCallMessageIndex = i;
                break;
            }
        }

        if (lastToolCallMessageIndex !== -1) {
            const msg = messages[lastToolCallMessageIndex];
            msg.action.data.result = data.content.result;
            msg.action.data.isResult = true;
            console.log(`[TOOL_RESULT] ✅ Matched message ${lastToolCallMessageIndex} (action.type="${msg.action.type}")`);
            console.log(`  result type: ${typeof msg.action.data.result}`);
        } else {
            console.log(`[TOOL_RESULT] ❌ No matching TOOL_CALL found for "${data.content.tool_name}"`);
            console.log(`  Available action types: ${messages.map(m => m.action?.type)}`);
        }
    }
}

// =============================================================================
// Simulate agent-controller.tsx filtering
// =============================================================================
console.log('\n' + '='.repeat(80));
console.log('AgentController Filter');
console.log('='.repeat(80));

const EXCLUDED_TYPES = [TOOL.TODO_WRITE, TOOL.TODO_READ, TOOL.COMPLETE, TOOL.FULLSTACK_PROJECT_INIT];

const actionMessages = messages.filter(m =>
    m.action && !EXCLUDED_TYPES.includes(m.action.type)
);

console.log(`\nTotal messages: ${messages.length}`);
console.log(`Action messages (after filter): ${actionMessages.length}`);

if (actionMessages.length === 0) {
    console.log('❌ No action messages — AgentController slider would be empty!');
} else {
    for (let i = 0; i < actionMessages.length; i++) {
        console.log(`  [${i}] type="${actionMessages[i].action.type}" isResult=${actionMessages[i].action.data.isResult}`);
    }
}

// =============================================================================
// Simulate agent-build.tsx rendering
// =============================================================================
console.log('\n' + '='.repeat(80));
console.log('AgentBuild Rendering Simulation');
console.log('='.repeat(80));

// Simulate selecting the last action (what AgentController dispatches)
const currentActionData = actionMessages.length > 0
    ? actionMessages[actionMessages.length - 1].action
    : null;

if (!currentActionData) {
    console.log('\n❌ No currentActionData — build panel would show nothing!');
    process.exit(1);
}

console.log(`\ncurrentActionData.type: "${currentActionData.type}"`);
console.log(`currentActionData.data keys: [${Object.keys(currentActionData.data).join(', ')}]`);

// --- Simulate tab computation ---
let tab = 'browser';
const type = currentActionData.type;

if ([TOOL.WEB_SEARCH, TOOL.WEB_BATCH_SEARCH, TOOL.TAVILY_SEARCH, TOOL.CRAWL, TOOL.IMAGE_SEARCH].includes(type)) {
    tab = 'search_browser';
}
console.log(`Tab: "${tab}"`);

// --- Simulate buildingTitle ---
let buildingTitle = 'Processing';

if (type === TOOL.WEB_SEARCH || type === TOOL.WEB_BATCH_SEARCH) {
    const toolInput = currentActionData.data?.tool_input;
    const searchTerm = toolInput?.query ||
        (toolInput?.queries ? toolInput.queries.join(', ') : '');
    buildingTitle = `Searching: "${searchTerm}"`;
} else if (type === TOOL.TAVILY_SEARCH) {
    const toolInput = currentActionData.data?.tool_input;
    const searchTerm = toolInput?.query || '';
    buildingTitle = `Searching: "${searchTerm}"`;
}

console.log(`buildingTitle: "${buildingTitle}"`);

if (buildingTitle.includes('""')) {
    console.log('⚠️  Empty search term in buildingTitle!');
}

// --- Simulate searchBrowserProps ---
const result = currentActionData.data?.result;
console.log(`\nresult type: ${typeof result}`);
console.log(`result value (first 200 chars): ${String(result).substring(0, 200)}`);

let searchResults = undefined;
if (tab === 'search_browser' && result) {
    searchResults = parseJson(result);
}

console.log(`\nparseJson(result): ${searchResults === null ? 'null' : Array.isArray(searchResults) ? `Array(${searchResults.length})` : typeof searchResults}`);

if (searchResults === null && result) {
    console.log('❌ parseJson returned null — SearchBrowser will render NOTHING!');
    console.log('   This is the bug: result is not a valid JSON string');

    // Show what went wrong
    if (typeof result === 'object') {
        console.log(`   result is a ${typeof result} (${result?.constructor?.name}) — JS does JSON.parse("[object Object]") → null`);
        if (result?.content) {
            console.log(`   result.content exists (type: ${typeof result.content}) — backend should send this as result instead`);
            const inner = parseJson(result.content);
            console.log(`   parseJson(result.content): ${inner === null ? 'null' : Array.isArray(inner) ? `Array(${inner.length})` : typeof inner}`);
        }
    }
} else if (Array.isArray(searchResults)) {
    console.log(`✅ SearchBrowser will render ${searchResults.length} results:`);
    for (const item of searchResults) {
        console.log(`   - ${item.title || item.url || JSON.stringify(item).substring(0, 80)}`);
    }
} else {
    console.log(`⚠️  parseJson returned ${typeof searchResults}, but SearchBrowser expects Array`);
}

// --- Final summary ---
console.log('\n' + '='.repeat(80));
console.log('SUMMARY');
console.log('='.repeat(80));

const toolCallEvents = events.filter(e => e.type === 'tool_call');
const toolResultEvents = events.filter(e => e.type === 'tool_result');
const matchedResults = messages.filter(m => m.action?.data?.isResult);

console.log(`\nTool calls received:     ${toolCallEvents.length}`);
console.log(`Tool results received:   ${toolResultEvents.length}`);
console.log(`Results matched:         ${matchedResults.length}`);
console.log(`buildingTitle:           ${buildingTitle}`);
console.log(`SearchBrowser renders:   ${Array.isArray(searchResults) ? `✅ ${searchResults.length} results` : '❌ nothing (null)'}`);

const allPass = buildingTitle && !buildingTitle.includes('""') && Array.isArray(searchResults) && searchResults.length > 0;

console.log(`\nOverall: ${allPass ? '✅ BUILD PANEL WOULD RENDER CORRECTLY' : '❌ BUILD PANEL WOULD NOT RENDER'}`);
