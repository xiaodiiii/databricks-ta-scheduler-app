"""
Multi-Agent Scheduling System using LangGraph.

Agents:
1. CalendarAgent - Queries all SA calendars for availability
2. DistributionAgent - Analyzes workload and recommends fair assignment
3. SchedulingAgent - Makes final scheduling decision and creates the meeting

The agents work together to automatically find the best time slot and interviewer.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, TypedDict, Annotated
import operator
import pytz
import random

# LangGraph and LangChain imports (with fallback for demo mode)
try:
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    print("LangGraph not available - running in rule-based mode")

from services.interview_tracker import get_interview_tracker


class SchedulingState(TypedDict):
    """State passed between agents in the scheduling workflow."""
    # Input
    candidate_name: str
    candidate_email: str
    interview_type: str
    duration_minutes: int
    preferred_date_start: str
    preferred_date_end: str
    
    # Calendar Agent outputs
    all_sa_ids: List[str]
    available_slots: List[Dict]  # Slots with availability per SA
    
    # Distribution Agent outputs
    ranked_slots: List[Dict]  # Slots ranked by fairness
    recommended_slot: Optional[Dict]
    recommended_sa: Optional[str]
    reasoning: str
    
    # Scheduling Agent outputs
    final_assignment: Optional[Dict]
    status: str
    error: Optional[str]


class SchedulingAgentSystem:
    """
    Multi-agent system for intelligent interview scheduling.
    
    Can run in two modes:
    1. LLM Mode: Uses OpenAI/other LLM for intelligent decisions
    2. Rule-based Mode: Uses deterministic rules (when LLM not available)
    """
    
    def __init__(self, use_llm: bool = False):
        self.tracker = get_interview_tracker()
        self.use_llm = use_llm and LANGGRAPH_AVAILABLE and os.environ.get('OPENAI_API_KEY')
        
        if self.use_llm:
            self._init_llm_workflow()
        else:
            print("Running in rule-based mode (no LLM)")
    
    def _init_llm_workflow(self):
        """Initialize LangGraph workflow with LLM agents."""
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1  # Low temperature for consistent decisions
        )
        
        # Build the graph
        workflow = StateGraph(SchedulingState)
        
        # Add nodes
        workflow.add_node("calendar_agent", self._calendar_agent_node)
        workflow.add_node("distribution_agent", self._distribution_agent_node)
        workflow.add_node("scheduling_agent", self._scheduling_agent_node)
        
        # Define edges
        workflow.set_entry_point("calendar_agent")
        workflow.add_edge("calendar_agent", "distribution_agent")
        workflow.add_edge("distribution_agent", "scheduling_agent")
        workflow.add_edge("scheduling_agent", END)
        
        self.workflow = workflow.compile()
    
    # ==================== Agent Nodes ====================
    
    def _calendar_agent_node(self, state: SchedulingState) -> Dict:
        """
        Calendar Agent: Fetches availability from all SA calendars.
        """
        print("📅 Calendar Agent: Checking all SA calendars...")
        
        # Get all active SAs
        all_sas = self.tracker.get_all_sas()
        all_sa_ids = [sa['id'] for sa in all_sas]
        
        # Get available slots (using demo data or real calendar)
        available_slots = self._get_calendar_availability(
            sa_ids=all_sa_ids,
            start_date=state['preferred_date_start'],
            end_date=state['preferred_date_end'],
            duration_minutes=state['duration_minutes']
        )
        
        return {
            "all_sa_ids": all_sa_ids,
            "available_slots": available_slots
        }
    
    def _distribution_agent_node(self, state: SchedulingState) -> Dict:
        """
        Distribution Agent: Ranks slots and SAs by fairness.
        """
        print("⚖️ Distribution Agent: Analyzing workload distribution...")
        
        available_slots = state['available_slots']
        interview_type = state['interview_type']
        
        if not available_slots:
            return {
                "ranked_slots": [],
                "recommended_slot": None,
                "recommended_sa": None,
                "reasoning": "No available slots found in the date range."
            }
        
        # Get workload stats
        workload_stats = self.tracker.get_workload_stats(since_days=21)
        
        # Rank each slot
        ranked_slots = []
        for slot in available_slots:
            # Get SAs available for this slot
            available_sa_ids = [
                sa_id for sa_id, available in slot['availability'].items()
                if available
            ]
            
            if not available_sa_ids:
                continue
            
            # Rank SAs for this slot
            ranked_sas = self.tracker.rank_sas_for_assignment(
                available_sa_ids, 
                interview_type
            )
            
            if not ranked_sas:
                continue
            
            best_sa = ranked_sas[0]
            
            # Calculate slot score (based on best available SA)
            slot_score = best_sa['final_score']
            
            ranked_slots.append({
                **slot,
                'best_sa_id': best_sa['sa_id'],
                'best_sa_name': best_sa['sa_name'],
                'best_sa_score': slot_score,
                'best_sa_interview_count': best_sa['interview_count'],
                'specialty_match': best_sa.get('specialty_match', False),
                'all_ranked_sas': ranked_sas
            })
        
        # Sort by best SA score (highest first)
        ranked_slots.sort(key=lambda x: x['best_sa_score'], reverse=True)
        
        # Get recommendation
        if ranked_slots:
            recommended = ranked_slots[0]
            reasoning = self._generate_reasoning(recommended, workload_stats)
        else:
            recommended = None
            reasoning = "No suitable slot/SA combination found."
        
        return {
            "ranked_slots": ranked_slots,
            "recommended_slot": recommended,
            "recommended_sa": recommended['best_sa_id'] if recommended else None,
            "reasoning": reasoning
        }
    
    def _scheduling_agent_node(self, state: SchedulingState) -> Dict:
        """
        Scheduling Agent: Finalizes the assignment and creates the booking.
        """
        print("✅ Scheduling Agent: Finalizing assignment...")
        
        recommended_slot = state.get('recommended_slot')
        recommended_sa = state.get('recommended_sa')
        
        if not recommended_slot or not recommended_sa:
            return {
                "final_assignment": None,
                "status": "failed",
                "error": "No suitable slot or SA available"
            }
        
        # Create the interview record
        interview = self.tracker.add_interview(
            candidate_name=state['candidate_name'],
            candidate_email=state['candidate_email'],
            interview_type=state['interview_type'],
            scheduled_time=recommended_slot['start'],
            duration_minutes=state['duration_minutes'],
            assigned_sa_id=recommended_sa,
            notes=f"Auto-scheduled. {state.get('reasoning', '')}"
        )
        
        sa_info = self.tracker.get_sa(recommended_sa)
        
        final_assignment = {
            "interview_id": interview['id'],
            "candidate_name": state['candidate_name'],
            "candidate_email": state['candidate_email'],
            "interview_type": state['interview_type'],
            "scheduled_time": recommended_slot['start'],
            "scheduled_end": recommended_slot['end'],
            "date_display": recommended_slot['date'],
            "time_display": recommended_slot['time'],
            "duration_minutes": state['duration_minutes'],
            "assigned_sa_id": recommended_sa,
            "assigned_sa_name": sa_info['name'] if sa_info else 'Unknown',
            "assigned_sa_email": sa_info['email'] if sa_info else '',
            "reasoning": state.get('reasoning', '')
        }
        
        return {
            "final_assignment": final_assignment,
            "status": "success",
            "error": None
        }
    
    # ==================== Helper Methods ====================
    
    def _get_calendar_availability(
        self,
        sa_ids: List[str],
        start_date: str,
        end_date: str,
        duration_minutes: int
    ) -> List[Dict]:
        """
        Get calendar availability for all SAs.
        Currently uses simulated data; will connect to real Google Calendar.
        """
        from dateutil import parser as date_parser
        
        # Parse dates
        if isinstance(start_date, str):
            start = date_parser.parse(start_date).date()
        else:
            start = start_date
        
        if isinstance(end_date, str):
            end = date_parser.parse(end_date).date()
        else:
            end = end_date
        
        tz = pytz.timezone('America/Los_Angeles')
        slots = []
        current = start
        
        # Try to use real calendar service
        try:
            from services.calendar_service import get_calendar_service
            cal_service = get_calendar_service()
            
            if cal_service.is_authenticated():
                # Use real calendar data
                # Map SA IDs to calendar IDs
                sa_calendar_map = {}
                for sa in self.tracker.get_all_sas():
                    sa_calendar_map[sa['id']] = sa.get('calendar_id', sa['email'])
                
                calendar_ids = list(sa_calendar_map.values())
                
                start_dt = tz.localize(datetime.combine(start, datetime.min.time().replace(hour=9)))
                end_dt = tz.localize(datetime.combine(end, datetime.min.time().replace(hour=17)))
                
                real_slots = cal_service.find_available_slots(
                    calendar_ids=calendar_ids,
                    start_date=start_dt,
                    end_date=end_dt,
                    slot_duration_minutes=duration_minutes
                )
                
                # Map calendar IDs back to SA IDs
                for slot in real_slots:
                    sa_availability = {}
                    for sa_id, cal_id in sa_calendar_map.items():
                        sa_availability[sa_id] = slot['availability'].get(cal_id, False)
                    slot['availability'] = sa_availability
                
                return real_slots
        except Exception as e:
            print(f"Calendar service error, using simulated data: {e}")
        
        # Fall back to simulated availability
        # Get all scheduled interviews to check for conflicts
        scheduled_interviews = self.tracker.get_upcoming_interviews()
        
        # Build a map of SA -> list of busy time ranges
        sa_busy_times = {sa_id: [] for sa_id in sa_ids}
        for interview in scheduled_interviews:
            sa_id = interview.get('assigned_sa_id')
            if sa_id in sa_busy_times:
                try:
                    from dateutil import parser as dt_parser
                    interview_start = dt_parser.parse(interview['scheduled_time'])
                    interview_duration = interview.get('duration_minutes', 60)
                    interview_end = interview_start + timedelta(minutes=interview_duration)
                    sa_busy_times[sa_id].append((interview_start, interview_end))
                except Exception as e:
                    print(f"Error parsing interview time: {e}")
        
        # Use seeded random for consistency but different per day
        while current <= end:
            if current.weekday() < 5:  # Skip weekends
                for hour in range(9, 17):
                    if hour + (duration_minutes / 60) <= 17:
                        slot_start = tz.localize(
                            datetime.combine(current, datetime.min.time().replace(hour=hour))
                        )
                        slot_end = slot_start + timedelta(minutes=duration_minutes)
                        
                        # Check availability for each SA
                        availability = {}
                        workload = self.tracker.get_interview_counts(since_days=21)
                        
                        for sa_id in sa_ids:
                            # First check if SA has a scheduled interview at this time
                            is_booked = False
                            for busy_start, busy_end in sa_busy_times.get(sa_id, []):
                                # Check for overlap
                                if not (slot_end <= busy_start or slot_start >= busy_end):
                                    is_booked = True
                                    break
                            
                            if is_booked:
                                availability[sa_id] = False
                            else:
                                # Base availability ~80% (simulate other meetings)
                                # Reduce slightly if overloaded
                                count = workload.get(sa_id, 0)
                                base_prob = 0.8 - (count * 0.02)
                                base_prob = max(0.5, min(0.95, base_prob))
                                
                                # Add some randomness based on day/hour
                                seed = hash(f"{current}_{hour}_{sa_id}") % 1000
                                random.seed(seed)
                                availability[sa_id] = random.random() < base_prob
                        
                        # Only include if at least one SA available
                        if any(availability.values()):
                            slots.append({
                                'start': slot_start.isoformat(),
                                'end': slot_end.isoformat(),
                                'date': current.strftime('%Y-%m-%d'),
                                'time': slot_start.strftime('%I:%M %p'),
                                'availability': availability
                            })
            
            current += timedelta(days=1)
        
        # Reset random seed
        random.seed()
        return slots
    
    def _generate_reasoning(self, slot: Dict, workload_stats: Dict) -> str:
        """Generate human-readable reasoning for the recommendation."""
        sa_id = slot['best_sa_id']
        sa_name = slot['best_sa_name']
        sa_stats = workload_stats.get(sa_id, {})
        
        interview_count = sa_stats.get('interview_count', 0)
        deviation = sa_stats.get('deviation', 0)
        specialty_match = slot.get('specialty_match', False)
        
        reasons = []
        
        if deviation < 0:
            reasons.append(f"{sa_name} has conducted {interview_count} interviews in the last 3 weeks, which is {abs(deviation):.1f} below the team average")
        elif deviation == 0:
            reasons.append(f"{sa_name} has conducted exactly the fair share of interviews")
        else:
            reasons.append(f"{sa_name} is slightly above average but is the best available option")
        
        if specialty_match:
            reasons.append("their specialty matches this interview type")
        
        reasons.append(f"available at {slot['time']} on {slot['date']}")
        
        return f"Recommended {sa_name} because: " + "; ".join(reasons) + "."
    
    # ==================== Public API ====================
    
    def schedule_interview(
        self,
        candidate_name: str,
        candidate_email: str,
        interview_type: str,
        duration_minutes: int = 60,
        preferred_date_start: Optional[str] = None,
        preferred_date_end: Optional[str] = None
    ) -> Dict:
        """
        Automatically schedule an interview using the multi-agent system.
        
        Args:
            candidate_name: Name of the candidate
            candidate_email: Email of the candidate
            interview_type: Type of interview
            duration_minutes: Duration of interview
            preferred_date_start: Start of date range (default: today)
            preferred_date_end: End of date range (default: 7 days from now)
            
        Returns:
            Dict with scheduling result including assigned SA and time
        """
        # Set default dates
        tz = pytz.timezone('America/Los_Angeles')
        now = datetime.now(tz)
        
        if not preferred_date_start:
            preferred_date_start = now.date().isoformat()
        if not preferred_date_end:
            preferred_date_end = (now + timedelta(days=7)).date().isoformat()
        
        # Initial state
        initial_state: SchedulingState = {
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "interview_type": interview_type,
            "duration_minutes": duration_minutes,
            "preferred_date_start": preferred_date_start,
            "preferred_date_end": preferred_date_end,
            "all_sa_ids": [],
            "available_slots": [],
            "ranked_slots": [],
            "recommended_slot": None,
            "recommended_sa": None,
            "reasoning": "",
            "final_assignment": None,
            "status": "pending",
            "error": None
        }
        
        if self.use_llm and hasattr(self, 'workflow'):
            # Run LangGraph workflow
            result = self.workflow.invoke(initial_state)
        else:
            # Run agents sequentially in rule-based mode
            result = initial_state
            result.update(self._calendar_agent_node(result))
            result.update(self._distribution_agent_node(result))
            result.update(self._scheduling_agent_node(result))
        
        return result
    
    def get_scheduling_preview(
        self,
        interview_type: str,
        duration_minutes: int = 60,
        preferred_date_start: Optional[str] = None,
        preferred_date_end: Optional[str] = None,
        top_n: int = 5
    ) -> Dict:
        """
        Get a preview of scheduling options without actually booking.
        
        Returns top N recommendations with reasoning.
        """
        tz = pytz.timezone('America/Los_Angeles')
        now = datetime.now(tz)
        
        if not preferred_date_start:
            preferred_date_start = now.date().isoformat()
        if not preferred_date_end:
            preferred_date_end = (now + timedelta(days=7)).date().isoformat()
        
        # Get all SAs
        all_sas = self.tracker.get_all_sas()
        all_sa_ids = [sa['id'] for sa in all_sas]
        
        # Get availability
        available_slots = self._get_calendar_availability(
            sa_ids=all_sa_ids,
            start_date=preferred_date_start,
            end_date=preferred_date_end,
            duration_minutes=duration_minutes
        )
        
        # Rank slots
        workload_stats = self.tracker.get_workload_stats(since_days=21)
        
        ranked_slots = []
        for slot in available_slots:
            available_sa_ids = [
                sa_id for sa_id, available in slot['availability'].items()
                if available
            ]
            
            if not available_sa_ids:
                continue
            
            ranked_sas = self.tracker.rank_sas_for_assignment(
                available_sa_ids, 
                interview_type
            )
            
            if ranked_sas:
                best_sa = ranked_sas[0]
                ranked_slots.append({
                    **slot,
                    'best_sa_id': best_sa['sa_id'],
                    'best_sa_name': best_sa['sa_name'],
                    'best_sa_score': best_sa['final_score'],
                    'best_sa_interview_count': best_sa['interview_count'],
                    'specialty_match': best_sa.get('specialty_match', False),
                    'reasoning': self._generate_reasoning(
                        {**slot, 'best_sa_id': best_sa['sa_id'], 'best_sa_name': best_sa['sa_name'], 'specialty_match': best_sa.get('specialty_match', False)},
                        workload_stats
                    )
                })
        
        ranked_slots.sort(key=lambda x: x['best_sa_score'], reverse=True)
        
        return {
            "total_slots_found": len(available_slots),
            "recommendations": ranked_slots[:top_n],
            "workload_stats": workload_stats
        }


# Singleton getter
_agent_system = None

def get_scheduling_agent() -> SchedulingAgentSystem:
    """Get the singleton SchedulingAgentSystem instance."""
    global _agent_system
    if _agent_system is None:
        _agent_system = SchedulingAgentSystem(use_llm=False)  # Default to rule-based
    return _agent_system

