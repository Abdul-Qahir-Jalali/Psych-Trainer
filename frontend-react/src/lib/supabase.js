import { createClient } from '@supabase/supabase-js';

// Load directly from environment variables. If you use Vite, VITE_ prefixed environment 
// variables are available via import.meta.env. For this local project, we'll hardcode 
// or use fallback values based on the .env provided earlier.

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://xlkriwqjkbfepbuvsvch.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_xVLDBnTqgRAeTN1obV5veA_QxOJLdoV';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
