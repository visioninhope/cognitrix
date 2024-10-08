export interface MessageInterface {
    id?: string|number,
    role: string,
    content: string,
    image?: string,
    artifacts?: object|object[]
}

export interface AgentInterface extends Object {
    id: string,
    name: string,
    model: string,
    provider: string,
    tools?: string[]
}

export interface TaskInterface extends Object {
    id?: string,
    title: string,
    description: string,
    step_instructions?: object,
    status: string,
    done: boolean
}

export interface SessionInterface {
    id: string,
    agent_id: string,
    chat: object[],
    datetime: string
}

export interface ProviderInterface extends Object {
    provider: string,
    model: string,
    api_key: string,
    base_url?: string,
    temperature: Number,
    max_tokens?: Number,
    supports_system_prompt?: boolean,
    system_prompt?: string,
    is_multimodal: boolean,
    supports_tool_use: boolean,
    tools?: object[],
    chat_history?: object[],
    client?: string,
}

export interface ToolInterface extends Object {
    name: string,
    description: string,
    category: string,
    parameters: object
}

export interface AgentDetailInterface extends Object {
    id?: string,
    name: string,
    system_prompt: string,
    is_sub_agent: boolean,
    parent_id?: string,
    llm: ProviderInterface,
    tools?: ToolInterface[],
    autostart: boolean,
    task?: object,
    websocket?: WebSocket,
    verbose?: boolean
}

export interface TaskDetailInterface extends Object {
    id?: string,
    title: string,
    description: string,
    step_instructions?: object,
    agent_ids: string[],
    tools?: ToolInterface[],
    autostart: boolean,
    status: string,
    done: boolean,
    created_at?: string,
    started_at?: string,
    completed_at?: string,
    session_id?: string
}

export interface SSEMessage {
    type: string;
    content: any;
    action?: string;
    complete?: boolean;
}

export interface SSEState {
    event: string,
    message: SSEMessage | null;
    connected: boolean;
    error: Event | Error | null;
}
  
