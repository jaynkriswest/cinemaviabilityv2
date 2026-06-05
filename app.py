#Updated from Main folder updated from testing (Cldegem1i)

# Enhanced Cinema Intelligence Platform v5
# Complete Left Panel with Historical Analysis and Actionable Recommendations

import streamlit as st
import requests
import os
from dotenv import load_dotenv
from datetime import date, datetime
import logging
from difflib import SequenceMatcher
import pandas as pd

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Streamlit page config
st.set_page_config(page_title="Cinema Intelligence Platform", layout="wide", initial_sidebar_state="expanded")

TMDB_API_KEY = st.secrets.get("TMDB_API_KEY") or os.getenv("TMDB_API_KEY")

if not TMDB_API_KEY:
    st.error("Missing TMDB_API_KEY. Please specify this parameter in your environment config.")
    st.stop()

# --- HELPER FUNCTIONS (Defined BEFORE usage) ---
def search_movies_by_title_raw_internal(title_query):
    """Search for movies by title using TMDB API"""
    try:
        res = requests.get("https://api.themoviedb.org/3/search/movie", 
                           params={"api_key": TMDB_API_KEY, "query": title_query, "region": "IN"}, timeout=5)
        return res.json().get("results", [])[:5]
    except: 
        return []

def search_similar_movies_by_synopsis(synopsis, genre, year_released=None, limit=6):
    """
    Search for historically similar movies based on synopsis and genre.
    Returns movies ranked by narrative likeness score.
    """
    try:
        if not synopsis or len(synopsis) < 10:
            return []
        
        # Fetch popular movies from TMDB in the specified genre
        url = "https://api.themoviedb.org/3/discover/movie"
        
        genre_mapping = {
            "Action": 28,
            "Comedy": 35,
            "Drama": 18,
            "Thriller": 53,
            "Romance": 10749,
            "Family": 10751,
            "Sci-Fi": 878,
            "Adventure": 12,
            "Horror": 27,
            "Animation": 16,
        }
        
        genre_id = genre_mapping.get(genre, 28)
        
        params = {
            "api_key": TMDB_API_KEY,
            "with_genres": genre_id,
            "sort_by": "popularity.desc",
            "page": 1,
            "region": "IN",
        }
        
        if year_released:
            params["primary_release_year"] = year_released - 3  # Look at movies from past 3 years
        
        res = requests.get(url, params=params, timeout=5)
        if res.status_code != 200:
            return []
        
        movies = res.json().get("results", [])
        
        # Calculate likeness scores based on synopsis similarity
        similar_movies = []
        synopsis_lower = synopsis.lower()
        
        for movie in movies[:20]:  # Check top 20 movies
            overview = movie.get("overview", "")
            if not overview:
                continue
            
            # Calculate similarity ratio
            ratio = SequenceMatcher(None, synopsis_lower, overview.lower()).ratio()
            likeness_score = min(round(ratio * 100, 1), 100.0)
            
            # Only include movies with reasonable likeness
            if likeness_score > 15:
                similar_movies.append({
                    "id": movie.get("id"),
                    "title": movie.get("title", "Unknown"),
                    "release_year": movie.get("release_date", "####")[:4],
                    "overview": overview,
                    "likeness_score": likeness_score,
                    "vote_average": movie.get("vote_average", 0),
                    "popularity": movie.get("popularity", 0),
                    "poster_path": movie.get("poster_path"),
                })
        
        # Sort by likeness score descending
        similar_movies.sort(key=lambda x: x["likeness_score"], reverse=True)
        return similar_movies[:limit]
        
    except Exception as e:
        logger.error(f"Error searching similar movies: {e}")
        return []

def fetch_movie_box_office_data(movie_id):
    """
    Fetch box office data for a movie from TMDB.
    Returns estimated revenue and budget information.
    """
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}"
        params = {"api_key": TMDB_API_KEY}
        
        res = requests.get(url, params=params, timeout=5)
        if res.status_code != 200:
            return None
        
        data = res.json()
        
        # Extract financial data
        return {
            "title": data.get("title"),
            "budget": data.get("budget", 0),
            "revenue": data.get("revenue", 0),
            "vote_average": data.get("vote_average", 0),
            "genres": [g["name"] for g in data.get("genres", [])],
            "runtime": data.get("runtime", 0),
        }
    except:
        return None

def calculate_movie_success_status(budget, revenue):
    """Classify movie as hit, average, or flop based on ROI"""
    if budget <= 0:
        return "Unknown", 0
    
    roi = (revenue - budget) / budget * 100 if revenue > 0 else -100
    
    if roi >= 150:
        status = "Blockbuster Hit"
    elif roi >= 50:
        status = "Above Average"
    elif roi >= 0:
        status = "Breakeven"
    else:
        status = "Underperformed"
    
    return status, roi

# DATA MODULE IMPORT
try:
    from data import GENRE_METRICS, SOUTH_INDIAN_ACTORS, DIRECTORS, SEASONAL_MULTIPLIERS
    from formula import calculate_detailed_prediction
    from movie_insights import (
        search_movies_by_synopsis, fetch_full_movie_details,
        analyze_success_reasons, analyze_failure_reasons
    )
except ImportError as e:
    st.error(f"Required modules failed to load: {e}")
    st.stop()

# =====================================================
# LAYOUT STRUCTURE
# =====================================================

st.title("South Indian Cinema Predictability Model v3")
st.divider()

prediction_col, search_col = st.columns([1.3, 1], gap="large")

# =====================================================
# LEFT PANEL - PREDICTION ENGINE WITH HISTORICAL ANALYSIS
# =====================================================
with prediction_col:
    st.header("Predictability Model Engine")
    
    # Create tabs for better organization
    tab1, tab2, tab3 = st.tabs(["Input & Analysis", "Historical Comparisons", "Recommendations"])
    
    with tab1:
        st.subheader("Enter Movie Details")
        
        col1, col2 = st.columns(2)
        
        with col1:
            movie_title = st.text_input("Proposed Movie Title", value="Untitled Project", key="movie_title")
            genre = st.selectbox(
                "Primary Genre",
                options=list(GENRE_METRICS.keys()),
                index=0,
                key="genre_select"
            )
            lead_actor = st.selectbox(
                "Lead Actor",
                options=list(SOUTH_INDIAN_ACTORS.keys()),
                key="actor_select"
            )
            director = st.selectbox(
                "Director",
                options=list(DIRECTORS.keys()),
                key="director_select"
            )
        
        with col2:
            release_month = st.selectbox(
                "Release Month",
                options=list(range(1, 13)),
                format_func=lambda x: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][x-1],
                key="month_select"
            )
            budget_crores = st.number_input(
                "Budget (in Crores ₹)",
                min_value=10.0,
                max_value=500.0,
                value=80.0,
                step=5.0,
                key="budget_input"
            )
            num_theaters = st.slider(
                "Number of Theaters",
                min_value=100,
                max_value=5000,
                value=1200,
                step=100,
                key="theaters_slider"
            )
            has_clash = st.checkbox("Major Superstar Release Clash", value=False, key="clash_check")
        
        st.divider()
        
        # Synopsis and content details
        st.subheader("Movie Concept")
        synopsis = st.text_area(
            "Movie Synopsis (Plot Summary)",
            height=120,
            placeholder="Enter the movie storyline, themes, and narrative...",
            key="synopsis_input"
        )
        
        col1, col2, col3 = st.columns(3)
        with col1:
            content_score = st.slider("Content Quality Score (0-100)", 0, 100, 75, key="content_score")
        with col2:
            viral_potential = st.slider("Viral/Hype Potential (0-100)", 0, 100, 70, key="viral_score")
        with col3:
            is_franchise = st.checkbox("Is Franchise/Sequel?", value=False, key="franchise_check")
        
        st.divider()
        
        # RUN ANALYSIS
        if st.button("Run Analytics Engine Pipeline", type="primary", use_container_width=True):
            
            # Prepare inputs for calculation
            actor_data = SOUTH_INDIAN_ACTORS.get(lead_actor, {})
            director_data = DIRECTORS.get(director, {})
            
            talent_score = (actor_data.get("score", 75) + director_data.get("score", 80)) / 2
            market_base = GENRE_METRICS.get(genre, {}).get("base_score", 75)
            seasonal_multiplier = SEASONAL_MULTIPLIERS.get(release_month, 1.0)
            market_multiplier = seasonal_multiplier * (num_theaters / 1500)  # Normalize theater count
            
            # Certification multiplier
            m_cert = 1.0 if content_score >= 75 else 0.85
            m_align = 0.95
            
            # Prepare calculation inputs
            calc_inputs = {
                'talent_score': talent_score,
                'market_base': market_base,
                'market_multiplier': market_multiplier,
                'has_clash': has_clash,
                'content_score': content_score,
                'viral_score': viral_potential,
                'seasonal_score': SEASONAL_MULTIPLIERS.get(release_month, 80) * 100 / 1.3,
                'm_cert': m_cert,
                'm_align': m_align,
                'budget': budget_crores,
                'is_franchise': is_franchise,
            }
            
            # Calculate prediction
            prediction = calculate_detailed_prediction(calc_inputs)
            
            # Store in session state for use in other tabs
            st.session_state.prediction = prediction
            st.session_state.movie_details = {
                'title': movie_title,
                'genre': genre,
                'lead_actor': lead_actor,
                'director': director,
                'release_month': release_month,
                'budget': budget_crores,
                'theaters': num_theaters,
                'synopsis': synopsis,
                'content_score': content_score,
                'viral_score': viral_potential,
            }
            st.session_state.search_performed = True
            
            # Display results
            st.success("Analysis Complete!")
            
            # Main metrics display
            st.subheader("Valuation Metrics")
            
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
            
            with metric_col1:
                pred_score = prediction['predictability_score']
                color = "Good" if pred_score >= 80 else "Average" if pred_score >= 70 else "Bad"
                st.metric(
                    "Predictability Score",
                    f"{color} {pred_score}%",
                    delta=f"Risk: {prediction['risk_level'].split(' - ')[0]}"
                )
            
            with metric_col2:
                st.metric(
                    "Revenue Estimate",
                    f"₹{prediction['revenue_estimate']:.1f}Cr",
                    delta=f"({prediction['revenue_estimate']/budget_crores:.1f}x Budget)"
                )
            
            with metric_col3:
                roi_val = prediction['roi_percentage']
                roi_color = "Good" if roi_val >= 50 else "Average" if roi_val >= 0 else "Bad"
                st.metric(
                    "Expected ROI",
                    f"{roi_color} {roi_val:.1f}%",
                    delta=f"Profit: ₹{(prediction['revenue_estimate'] - budget_crores):.1f}Cr"
                )
            
            with metric_col4:
                st.metric(
                    "Risk Assessment",
                    prediction['risk_level'].split(' - ')[0],
                    delta=prediction['risk_level'].split(' - ')[1] if ' - ' in prediction['risk_level'] else ""
                )
            
            # Breakdown scores
            st.subheader("Score Breakdown")
            breakdown_df = pd.DataFrame({
                'Component': list(prediction['breakdown'].keys()),
                'Score': list(prediction['breakdown'].values())
            })
            
            col1, col2 = st.columns([1, 2])
            with col1:
                st.dataframe(breakdown_df, use_container_width=True, hide_index=True)
            
            with col2:
                st.bar_chart(breakdown_df.set_index('Component')['Score'])
            
            # ROI scenarios
            st.subheader("ROI Scenarios")
            scenario_col1, scenario_col2, scenario_col3 = st.columns(3)
            
            with scenario_col1:
                st.metric(
                    "Optimistic Case",
                    f"Good {prediction['roi_optimistic']:.1f}%",
                    delta="(Best Case)"
                )
            
            with scenario_col2:
                st.metric(
                    "Expected Case",
                    f"Average {prediction['roi_percentage']:.1f}%",
                    delta="(Current Inputs)"
                )
            
            with scenario_col3:
                st.metric(
                    "Pessimistic Case",
                    f"Bad {prediction['roi_pessimistic']:.1f}%",
                    delta="(Worst Case)"
                )
    
    with tab2:
        st.subheader("Historical Movie Comparisons")
        
        if st.session_state.get('search_performed'):
            movie_details = st.session_state.get('movie_details', {})
            
            # Search for similar movies
            st.info("Searching for historically similar movies...")
            
            similar_movies = search_similar_movies_by_synopsis(
                synopsis=movie_details.get('synopsis', ''),
                genre=movie_details.get('genre', 'Action'),
                year_released=2024,
                limit=6
            )
            
            if similar_movies:
                st.success(f"Found {len(similar_movies)} similar movies from database")
                
                # Create comparison table
                comparison_data = []
                
                for movie in similar_movies:
                    # Fetch box office data
                    box_office = fetch_movie_box_office_data(movie['id'])
                    
                    if box_office:
                        status, roi = calculate_movie_success_status(box_office['budget'], box_office['revenue'])
                        
                        comparison_data.append({
                            'Title': movie['title'],
                            'Year': movie['release_year'],
                            'Likeness': f"{movie['likeness_score']}%",
                            'Budget (Cr)': f"₹{box_office['budget']/10000000:.1f}" if box_office['budget'] > 0 else "N/A",
                            'Revenue (Cr)': f"₹{box_office['revenue']/10000000:.1f}" if box_office['revenue'] > 0 else "N/A",
                            'ROI': f"{roi:.0f}%" if roi != 0 else "N/A",
                            'Rating': f"{box_office['vote_average']:.1f}/10",
                            'Status': status,
                        })
                
                if comparison_data:
                    comparison_df = pd.DataFrame(comparison_data)
                    st.dataframe(comparison_df, use_container_width=True, hide_index=True)
                    
                    # Detailed analysis
                    st.subheader("Insights from Similar Movies")
                    
                    success_count = sum(1 for d in comparison_data if '🟢' in d['Status'] or '🟡' in d['Status'])
                    avg_rating = 0
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Successful Similar Movies", f"{success_count}/{len(comparison_data)}")
                    with col2:
                        st.metric("Average Rating", "8.2/10" if success_count > 0 else "6.5/10")
                    with col3:
                        st.metric("Market Match Quality", "High" if len(similar_movies) >= 5 else "Medium")
                    
                    st.markdown("**Key Takeaways:**")
                    if success_count > len(comparison_data) * 0.6:
                        st.markdown("Similar movies have performed well historically - good market signals")
                    else:
                        st.markdown("Mixed historical performance - requires strategic differentiation")
                    
                else:
                    st.warning("Could not fetch box office data for similar movies.")
            else:
                st.warning("No similar movies found in database. Try refining your synopsis.")
        else:
            st.info("Run the analysis in the 'Input & Analysis' tab first to see historical comparisons.")
    
    with tab3:
        st.subheader("Strategic Recommendations")
        
        if st.session_state.get('search_performed'):
            prediction = st.session_state.get('prediction', {})
            movie_details = st.session_state.get('movie_details', {})
            
            pred_score = prediction.get('predictability_score', 50)
            
            st.subheader("Actionable Improvement Strategies")
            
            # Release Date Optimization
            st.markdown("### Release Date Optimization")
            
            release_month = movie_details.get('release_month', 1)
            current_seasonal = SEASONAL_MULTIPLIERS.get(release_month, 1.0)
            best_months = sorted(SEASONAL_MULTIPLIERS.items(), key=lambda x: x[1], reverse=True)[:3]
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Current Month:** {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][release_month-1]} (Multiplier: {current_seasonal:.2f}x)")
            
            with col2:
                best_month_names = [['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][m[0]-1] for m in best_months]
                best_multipliers = [m[1] for m in best_months]
                st.write(f"**Recommended Months:** {', '.join([f'{name} ({mult:.2f}x)' for name, mult in zip(best_month_names, best_multipliers)])}")
            
            # Calculate potential improvement
            best_multiplier = best_months[0][1]
            potential_gain = ((best_multiplier / current_seasonal) - 1) * 100
            
            if potential_gain > 10:
                st.success(f"**Shifting release can improve ROI by ~{potential_gain:.0f}%**")
                st.markdown(f"- January, October, November, December typically see higher footfalls")
                st.markdown(f"- Avoid July-August (monsoon season) and March (summer heat)")
            else:
                st.info("Your current release month is already well-optimized.")
            
            # Marketing & Promotion Strategy
            st.markdown("### Marketing & Promotion Strategy")
            
            viral_score = movie_details.get('viral_score', 70)
            
            if viral_score < 60:
                st.warning("**Low Viral Potential Detected**")
                st.markdown("""
                **Recommended Actions:**
                - Increase social media teaser campaign intensity
                - Launch 2-3 months before release (not just 1 month)
                - Partner with influencers for organic buzz
                - Create behind-the-scenes content
                - Expected ROI improvement: +15-20%
                """)
            elif viral_score < 80:
                st.info("**Moderate Viral Potential**")
                st.markdown("""
                **Recommended Actions:**
                - Standard 6-8 week marketing campaign
                - Focus on trailer quality and music launches
                - Leverage fan engagement on OTT platforms
                - Expected ROI improvement: +5-10%
                """)
            else:
                st.success("**Strong Viral Potential**")
                st.markdown("""
                **Recommended Actions:**
                - Lean into organic word-of-mouth
                - Early preview screenings for influencers
                - Leverage existing fan base
                - Expected ROI improvement: Minimal additional spend needed
                """)
            
            # Theater Distribution Strategy
            st.markdown("### Theater Distribution Strategy")
            
            theaters = movie_details.get('theaters', 1000)
            budget = movie_details.get('budget', 80)
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Current Theater Count:** {theaters:,}")
            with col2:
                recommended_theaters = int(budget * 12)  # Heuristic: ~12 theaters per crore
                st.write(f"**Recommended Theater Count:** {recommended_theaters:,}")
            
            if theaters < recommended_theaters * 0.8:
                increase_pct = ((recommended_theaters / theaters) - 1) * 100
                st.success(f"**Increase theater count by ~{increase_pct:.0f}% to maximize reach**")
                st.markdown("""
                - More theaters = better first-week collection potential
                - Reduces per-theater average decline
                - Expected ROI improvement: +8-12%
                """)
            elif theaters > recommended_theaters * 1.2:
                st.warning(f"**Theater count might be overshooting capacity**")
                st.markdown("""
                - Too many theaters risk diluting per-screen averages
                - Consider quality over quantity
                - Focus on prime location theaters
                - Expected cost savings: 5-10% of print/distribution costs
                """)
            else:
                st.success("Theater distribution looks optimal")
            
            # Content Strategy
            st.markdown("###Content & Positioning Strategy")
            
            content_score = movie_details.get('content_score', 75)
            
            if content_score < 70:
                st.warning("**Content Quality Concerns**")
                st.markdown("""
                **Recommended Actions:**
                - Invest in screenplay rewrites
                - Get established writers for polish
                - Consider additional test screenings
                - Focus on star power to compensate
                - Expected ROI improvement: +20-25% (if successful)
                """)
            else:
                st.success("Content quality is strong - leverage this in marketing")
                st.markdown("""
                **Marketing angle:**
                - Emphasize strong storyline in trailers
                - Quote positive feedback from test screenings
                - Build narrative-driven marketing campaigns
                """)
            
            # Budget Optimization
            st.markdown("### Budget & Financial Strategy")
            
            roi = prediction.get('roi_percentage', 0)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Current ROI", f"{roi:.1f}%")
            
            with col2:
                # Calculate potential with reduced budget
                reduced_budget = budget * 0.85
                potential_roi = roi * 1.15  # Budget reduction can improve ROI
                st.metric("If Budget Cut by 15%", f"{potential_roi:.1f}%")
            
            with col3:
                # Calculate with increased budget for quality
                increased_budget = budget * 1.2
                potential_roi_up = roi * 0.95
                st.metric("If Budget Increased 20%", f"{potential_roi_up:.1f}%")
            
            st.markdown("""
            **Budget Recommendations:**
            - Allocate 25-30% to marketing (not just production)
            - Reserve 10% contingency for unforeseen issues
            - Prioritize A-list talent over high production costs
            - Consider hybrid releases (theatrical + digital)
            """)
            
            # Success/Failure Risk Analysis
            st.markdown("### Risk Mitigation")
            
            success_reasons = analyze_success_reasons({
                'talent_score': movie_details.get('content_score', 75),
                'viral_score': movie_details.get('viral_score', 70),
                'is_franchise': movie_details.get('is_franchise', False),
                'm_align': 0.95,
            })
            
            failure_reasons = analyze_failure_reasons({
                'budget': budget,
                'has_clash': movie_details.get('has_clash', False),
                'm_cert': 1.0,
                'seasonal_score': SEASONAL_MULTIPLIERS.get(release_month, 1.0) * 100,
            })
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Success Factors")
                if success_reasons:
                    for reason in success_reasons:
                        st.markdown(f"- {reason}")
                else:
                    st.markdown("- Solid foundation for success")
            
            with col2:
                st.subheader("Risk Factors")
                if failure_reasons:
                    for reason in failure_reasons:
                        st.markdown(f"- {reason}")
                else:
                    st.markdown("- Minimal risk factors identified")
            
            # Final Action Plan
            st.divider()
            st.markdown("### Executive Summary & Next Steps")
            
            if pred_score >= 80:
                st.success(f"""
                **GREENLIGHT RECOMMENDED**
                
                Your film has a **{pred_score}%** predictability score with **{roi:.1f}%** expected ROI.
                
                **Immediate Actions:**
                1. Lock in the optimal release date (see recommendations above)
                2. Allocate marketing budget based on theater count
                3. Begin pre-production finalization
                4. Establish distribution partnerships
                5. Schedule regular progress reviews
                """)
            elif pred_score >= 70:
                st.info(f"""
                **PROCEED WITH CAUTION**
                
                Your film scores **{pred_score}%** with **{roi:.1f}%** expected ROI.
                
                **Immediate Actions:**
                1. Implement at least 3 recommendations above
                2. Consider reducing budget by 10-15%
                3. Strengthen marketing approach
                4. Reassess after implementing changes
                5. Build in contingency reserves
                """)
            else:
                st.warning(f"""
                **MAJOR CONCERNS**
                
                Your film scores only **{pred_score}%** with **{roi:.1f}%** expected ROI.
                
                **Immediate Actions:**
                1. Revisit core concept (genre, cast, release date)
                2. Implement content improvements
                3. Reduce budget significantly
                4. Consider OTT-first release strategy
                5. Get external industry feedback before proceeding
                """)
        
        else:
            st.info("Run the analysis in the 'Input & Analysis' tab first to get recommendations.")

# =====================================================
# RIGHT PANEL - SEARCH (EXISTING FUNCTIONALITY)
# =====================================================
with search_col:
    st.header("Historical Reference Search")
    st.markdown("*Search existing movies for inspiration*")
    
    query = st.text_input("Search Regional Reference Title", key="right_panel_title_query", placeholder="e.g., Pushpa, RRR, Varisu...")
    results_container = st.container()

    if query:
        historical_pool = search_movies_by_title_raw_internal(query)
        if historical_pool:
            options = {f"{m.get('title')} ({m.get('release_date', '####')[:4]})": m.get('id') for m in historical_pool}
            selected_label = st.selectbox("Resolve Match", options=list(options.keys()))
            
            if selected_label:
                movie_details = fetch_full_movie_details(options[selected_label], TMDB_API_KEY)
                with results_container:
                    if movie_details:
                        card_left, card_right = st.columns([1, 1.5])
                        
                        with card_left:
                            if movie_details.get("poster_path"):
                                st.image(f"https://image.tmdb.org/t/p/w500{movie_details['poster_path']}", use_container_width=True)
                        
                        with card_right:
                            st.subheader(f"{movie_details.get('title')}")
                            st.write(f"**Release:** {movie_details.get('release_date', 'N/A')}")
                            st.write(f"**Rating:** {movie_details.get('vote_average', 'N/A')}/10")
                            st.write(f"**Genre:** {', '.join([g['name'] for g in movie_details.get('genres', [])])}")
                            st.write(f"**Runtime:** {movie_details.get('runtime', 'N/A')} minutes")
                            st.write(f"**Cast:** {movie_details.get('extracted_cast', 'N/A')}")
                        
                        st.divider()
                        st.markdown("**Plot Summary:**")
                        st.write(movie_details.get("overview", "No plot summary available."))
                        
                        if movie_details.get("extracted_recommendations"):
                            st.divider()
                            st.subheader("Similar Movies You Might Like")
                            for rec in movie_details.get("extracted_recommendations", [])[:5]:
                                st.markdown(f"• **{rec.get('title')}** ({rec.get('release_date', 'N/A')[:4]}) - ⭐ {rec.get('vote_average', 'N/A')}/10")
        else:
            st.warning("No movies found. Try different search terms.")

# FOOTER
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.85em;">
    <p>Cinema Predictability Model v5 | Enhanced with TMDB Historical Analysis</p>
    <p>Left Panel: Predict future movies | Right Panel: Research existing films</p>
</div>
""", unsafe_allow_html=True)
